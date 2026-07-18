"""Tuning-layer candidate precompute: per query, every comp any searched
config could admit, with serving-computed term distances.

Term values come from evaluating app.services.comps._distance_terms
expressions in polars - the same engine and formulas that serve - so the
numpy scorer can only diverge in the (parity-tested) aggregation step,
never in a term definition. The superset filter must dominate every
geometry the random search can sample; search.py asserts that.
"""

from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from functools import reduce

import numpy as np
import polars as pl

from app.services.comps import _distance_terms
from app.services.constants import DEFAULT_RETRIEVAL
from pipeline.eval.availability import available_universe
from pipeline.eval.contexts import EvalQuery
from pipeline.eval.metrics import pinball_log_scalar

SUPERSET_AGE_BAND = 6.0
SUPERSET_VALUE_BRACKET = (0.2, 5.0)
SUPERSET_DEST_STRENGTH_BAND = 1.5  # must dominate every band the search samples
TERM_COUNT = 10
CLUB_TERM_INDICES = (4, 5, 6)  # elo, dest club value, origin club value: the drop set


@dataclass(frozen=True)
class CandidateSet:
    """One query's superset candidates as numpy arrays (NaN = missing)."""

    terms: np.ndarray  # (n, TERM_COUNT) float64, serving term order
    v_before: np.ndarray  # (n,) float64
    age: np.ndarray  # (n,) float64
    from_tier: np.ndarray  # (n,) float64
    to_strength: np.ndarray  # (n,) float64, baked as-of the comp's season
    multiplier: np.ndarray  # (n,) float64
    player_id: np.ndarray  # (n,) int64
    transfer_ord: np.ndarray  # (n,) int64, days since epoch
    value_eur: int
    query_age: float | None
    origin_tier: int | None
    dest_strength: float
    actual_multiplier: float
    actual_log: float
    fallback_pinball: float  # B1 pinball: what refusing this query scores


def _term_matrix(sup: pl.DataFrame, built: EvalQuery) -> np.ndarray:
    """(n, TERM_COUNT) with serving term order; a query-side-missing term is a
    NaN column, which the renormalizing scorer drops per comp - the exact
    equivalent of serving never adding the term."""
    query, dest_league, dest_club = built.query, built.dest_league, built.dest_club
    present = (
        True,  # log value
        query.age is not None,
        dest_league.strength is not None,
        query.origin_strength is not None,
        dest_club is not None and dest_club.elo_pct is not None,
        dest_club is not None and dest_club.club_value_pct is not None,
        query.origin_club_value_pct is not None,
        query.minutes_share is not None,
        query.player.sub_position is not None,
        True,  # recency
    )
    exprs = iter(
        expr
        for expr, _weight in _distance_terms(
            query, dest_league, dest_club, drop_club_terms=False, config=DEFAULT_RETRIEVAL
        )
    )
    columns = [
        (next(exprs) if flag else pl.lit(float("nan"))).cast(pl.Float64).alias(f"t{i}")
        for i, flag in enumerate(present)
    ]
    return sup.select(columns).to_numpy()


def _fallback_pinball(universe_t: pl.DataFrame, actual_log: float) -> float:
    multipliers = universe_t.get_column("multiplier")
    if multipliers.len() >= 2:
        quantiles = tuple(
            float(q)
            for q in (
                multipliers.quantile(tau, interpolation="linear") for tau in (0.25, 0.5, 0.75)
            )
            if q is not None
        )
    else:
        quantiles = (1.0, 1.0, 1.0)  # nothing quotable: value-unchanged prior
    assert len(quantiles) == 3
    return pinball_log_scalar(actual_log, (quantiles[0], quantiles[1], quantiles[2]))


def candidate_set(built: EvalQuery, universe: pl.DataFrame, season_min: int) -> CandidateSet:
    universe_t = available_universe(universe, built.transfer_date)
    query = built.query
    # build_eval_query skips strength-less destinations, so this is total.
    dest_strength = built.dest_league.strength
    assert dest_strength is not None
    conds = [
        pl.col("position_group") == query.player.position_group,
        pl.col("season") >= season_min,
        (pl.col("to_strength") - dest_strength).abs() <= SUPERSET_DEST_STRENGTH_BAND,
        pl.col("v_before").is_between(
            SUPERSET_VALUE_BRACKET[0] * query.value_eur * (1 - 1e-9),
            SUPERSET_VALUE_BRACKET[1] * query.value_eur * (1 + 1e-9),
        ),
    ]
    if query.age is not None:
        conds.append(
            pl.col("age_at_transfer").is_between(
                query.age - SUPERSET_AGE_BAND, query.age + SUPERSET_AGE_BAND
            )
        )
    sup = universe_t.filter(reduce(operator.and_, conds))
    actual_log = math.log(built.actual_multiplier)
    return CandidateSet(
        terms=_term_matrix(sup, built),
        v_before=sup.get_column("v_before").cast(pl.Float64).to_numpy(),
        age=sup.get_column("age_at_transfer").cast(pl.Float64).to_numpy(),
        from_tier=sup.get_column("from_tier").cast(pl.Float64).to_numpy(),
        to_strength=sup.get_column("to_strength").cast(pl.Float64).to_numpy(),
        multiplier=sup.get_column("multiplier").to_numpy(),
        player_id=sup.get_column("player_id").cast(pl.Int64).to_numpy(),
        transfer_ord=sup.get_column("transfer_date").cast(pl.Int32).to_numpy().astype(np.int64),
        value_eur=query.value_eur,
        query_age=query.age,
        origin_tier=query.origin_tier,
        dest_strength=dest_strength,
        actual_multiplier=built.actual_multiplier,
        actual_log=actual_log,
        fallback_pinball=_fallback_pinball(universe_t, actual_log),
    )
