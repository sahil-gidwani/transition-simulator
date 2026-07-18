"""LightGBM quantile skyline: the black-box reference that prices the
traceability tax. Offline only - it never serves.

Per rolling-origin fold (one per evaluated season), three quantile models
train on every transition observable before the fold season opens - the
same availability function as everywhere else, applied at July 1, coarser
than the runner's per-query date-exact rule and therefore conservative
AGAINST the skyline. Features mirror the information the distance terms
see; the target is the log multiplier; fixed honest hyperparameters, no
early stopping - it is a reference point, not a product.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import lightgbm as lgb
import numpy as np
import polars as pl

from app.repositories.store import DataStore
from pipeline.eval.availability import available_universe
from pipeline.eval.contexts import EvalQuery, SkippedQuery, build_eval_query
from pipeline.eval.records import PredictionRecord, records_frame
from pipeline.eval.splits import eval_rows

SEED = 20260718
ALPHAS = (0.25, 0.50, 0.75)
NUM_BOOST_ROUND = 400
BASE_PARAMS: dict[str, Any] = {
    "objective": "quantile",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "min_data_in_leaf": 50,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "seed": SEED,
    "deterministic": True,
    "verbosity": -1,
}

FEATURES = (
    "ln_v_before",
    "age_at_transfer",
    "position_code",
    "sub_position_code",
    "from_tier",
    "to_tier",
    "tier_diff",
    "from_strength",
    "to_strength",
    "from_club_value_pct",
    "to_club_value_pct",
    "from_elo_pct",
    "to_elo_pct",
    "minutes_share_pre",
    "season",
)
CATEGORICAL = ("position_code", "sub_position_code")


def _codes(universe: pl.DataFrame, column: str) -> dict[str, int]:
    values = sorted(universe.get_column(column).drop_nulls().unique().to_list())
    return {value: index for index, value in enumerate(values)}


def _feature_matrix(
    frame: pl.DataFrame,
    position_codes: dict[str, int],
    sub_position_codes: dict[str, int],
) -> np.ndarray:
    # Negative categorical codes are LightGBM's missing marker. Strengths and
    # club-value percentiles are baked into the transitions artifact.
    features = frame.select(
        ln_v_before=pl.col("v_before").log(),
        age_at_transfer=pl.col("age_at_transfer").cast(pl.Float64),
        position_code=pl.col("position_group")
        .replace_strict(position_codes, default=-1)
        .cast(pl.Float64),
        sub_position_code=pl.col("sub_position")
        .replace_strict(sub_position_codes, default=-1)
        .cast(pl.Float64),
        from_tier=pl.col("from_tier").cast(pl.Float64),
        to_tier=pl.col("to_tier").cast(pl.Float64),
        tier_diff=(pl.col("to_tier") - pl.col("from_tier")).cast(pl.Float64),
        from_strength=pl.col("from_strength").cast(pl.Float64),
        to_strength=pl.col("to_strength").cast(pl.Float64),
        from_club_value_pct=pl.col("from_club_value_pct").cast(pl.Float64),
        to_club_value_pct=pl.col("to_club_value_pct").cast(pl.Float64),
        from_elo_pct=pl.col("from_elo_pct").cast(pl.Float64),
        to_elo_pct=pl.col("to_elo_pct").cast(pl.Float64),
        minutes_share_pre=pl.col("minutes_share_pre").cast(pl.Float64),
        season=pl.col("season").cast(pl.Float64),
    )
    return features.to_numpy()


def run_skyline(store: DataStore, seasons: tuple[int, ...]) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(records, gain importances averaged across folds and quantiles)."""
    universe = store.transitions.comps_universe
    position_codes = _codes(universe, "position_group")
    sub_position_codes = _codes(universe, "sub_position")

    records: list[PredictionRecord] = []
    gain_sums = np.zeros(len(FEATURES))
    n_models = 0
    for season in seasons:
        # The day before the July-June season opens: coarser than the
        # runner's per-query rule, conservative against the skyline.
        train = available_universe(universe, date(season, 6, 30))
        if train.height < 200:
            raise RuntimeError(f"skyline fold {season}: only {train.height} training rows")
        x_train = _feature_matrix(train, position_codes, sub_position_codes)
        y_train = np.log(train.get_column("multiplier").to_numpy())
        dataset = lgb.Dataset(
            x_train,
            label=y_train,
            feature_name=list(FEATURES),
            categorical_feature=list(CATEGORICAL),
            free_raw_data=False,
            params={"verbosity": -1},
        )

        rows = eval_rows(universe, (season,))
        eligible_mask: list[bool] = []
        eligible: list[EvalQuery] = []
        for row in rows.iter_rows(named=True):
            built = build_eval_query(row, store.seasons)
            eligible_mask.append(not isinstance(built, SkippedQuery))
            if isinstance(built, EvalQuery):
                eligible.append(built)
        predict_frame = rows.filter(pl.Series(eligible_mask))
        x_predict = _feature_matrix(predict_frame, position_codes, sub_position_codes)

        predictions = []
        for alpha in ALPHAS:
            model = lgb.train(
                {**BASE_PARAMS, "alpha": alpha}, dataset, num_boost_round=NUM_BOOST_ROUND
            )
            predictions.append(np.asarray(model.predict(x_predict)))
            gain_sums += np.asarray(model.feature_importance(importance_type="gain"))
            n_models += 1
        # Post-hoc sort kills quantile crossing; exp back to multipliers.
        quantiles = np.exp(np.sort(np.stack(predictions, axis=1), axis=1))

        for built, (q25, q50, q75) in zip(eligible, quantiles, strict=True):
            records.append(
                PredictionRecord(
                    player_id=built.player_id,
                    transfer_date=built.transfer_date,
                    season=built.season,
                    v_before=built.v_before,
                    v_after=built.v_after,
                    actual_multiplier=built.actual_multiplier,
                    q25=float(q25),
                    q50=float(q50),
                    q75=float(q75),
                    insufficient=False,  # a regressor always answers
                    pool_size=0,
                    relaxation_level=0,
                    confidence="skyline",
                    iqr_log=None,
                    n_available=train.height,
                    b1_q25=None,
                    b1_q50=None,
                    b1_q75=None,
                    b2_q25=None,
                    b2_q50=None,
                    b2_q75=None,
                    b2_fallback=True,
                    age_at_transfer=built.age_at_transfer,
                    position_group=built.position_group,
                    from_tier=built.from_tier,
                    to_tier=built.to_tier,
                    minutes_known=built.minutes_known,
                    pool_multipliers=[],
                    pool_similarities=[],
                )
            )

    importances = pl.DataFrame(
        {"feature": list(FEATURES), "gain": (gain_sums / n_models).tolist()}
    ).sort("gain", descending=True)
    return records_frame(records), importances
