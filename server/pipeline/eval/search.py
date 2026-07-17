"""Random search over retrieval configs, scored on validation pinball.

The objective is the mean log pinball across q25/q50/q75 on validation
queries. A refused query (insufficient precedent) contributes its B1
fallback pinball - refusing scores exactly like quoting the naive global
range, so refusal cannot game the objective. Constraints keep the winner
honest: its refusal rate may not exceed the hand-set config's by more
than one point, and its pooled coverage must stay in a loose sanity band
(fine calibration is a later, separate stage).

The search never touches test seasons; the winner is frozen into
app/services/constants.py by hand (a reviewed chore commit), and only
then are test seasons scored, once.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass

from app.repositories.store import DataStore
from app.services.comps import find_comps
from app.services.constants import DEFAULT_RETRIEVAL, LadderStep, RetrievalConfig
from app.services.valuation import summarize_pool
from pipeline.eval.availability import available_universe
from pipeline.eval.candidates import (
    SUPERSET_AGE_BAND,
    SUPERSET_VALUE_BRACKET,
    candidate_set,
)
from pipeline.eval.contexts import EvalQuery, SkippedQuery, build_eval_query
from pipeline.eval.metrics import pinball_log_scalar
from pipeline.eval.scorer import score_query
from pipeline.eval.splits import VALIDATION_SEASONS, eval_rows

SEED_DEFAULT = 20260718
N_CONFIGS_DEFAULT = 300
INSUFFICIENT_TOLERANCE = 0.01  # winner may refuse at most 1pt more than hand-set
COVERAGE_BAND = (0.35, 0.65)  # loose sanity; calibration trims later
PARITY_TOLERANCE = 1e-9

WEIGHT_RANGE = (0.05, 2.0)
POOL_K_RANGE = (8, 48)
MIN_POOL_TARGET_RANGE = (2, 8)
BASE_AGE_BANDS = (2.0, 2.5, 3.0, 4.0)
WIDE_AGE_BANDS = (4.5, 5.0, 6.0)
BASE_BRACKETS_LO = (0.3, 0.4, 0.5)
BASE_BRACKETS_HI = (2.0, 2.5, 3.0)
WIDE_BRACKETS_LO = (0.2, 0.25)
WIDE_BRACKETS_HI = (4.0, 5.0)


def sample_config(rng: random.Random) -> RetrievalConfig:
    def log_uniform(bounds: tuple[float, float]) -> float:
        return math.exp(rng.uniform(math.log(bounds[0]), math.log(bounds[1])))

    base_age = rng.choice(BASE_AGE_BANDS)
    wide_age = rng.choice(WIDE_AGE_BANDS)
    base_bracket = (rng.choice(BASE_BRACKETS_LO), rng.choice(BASE_BRACKETS_HI))
    wide_bracket = (rng.choice(WIDE_BRACKETS_LO), rng.choice(WIDE_BRACKETS_HI))
    # The candidate precompute can only score geometries inside its superset.
    assert wide_age <= SUPERSET_AGE_BAND
    assert wide_bracket[0] >= SUPERSET_VALUE_BRACKET[0]
    assert wide_bracket[1] <= SUPERSET_VALUE_BRACKET[1]
    ladder = (
        LadderStep("base filters", base_age, base_bracket, 1),
        LadderStep(f"age band widened to +/-{wide_age:g} years", wide_age, base_bracket, 1),
        LadderStep(
            f"value bracket widened to {wide_bracket[0]:g}-{wide_bracket[1]:g}x",
            wide_age,
            wide_bracket,
            1,
        ),
        LadderStep("origin league tier widened to +/-2", wide_age, wide_bracket, 2),
        LadderStep(
            "origin league filter dropped; club-level terms ignored",
            wide_age,
            wide_bracket,
            None,
            drop_club_terms=True,
        ),
    )
    return RetrievalConfig(
        w_log_value=log_uniform(WEIGHT_RANGE),
        w_age=log_uniform(WEIGHT_RANGE),
        w_dest_strength=log_uniform(WEIGHT_RANGE),
        w_origin_strength=log_uniform(WEIGHT_RANGE),
        w_elo=log_uniform(WEIGHT_RANGE),
        w_dest_tercile=log_uniform(WEIGHT_RANGE),
        w_origin_tercile=log_uniform(WEIGHT_RANGE),
        w_minutes=log_uniform(WEIGHT_RANGE),
        w_sub_position=log_uniform(WEIGHT_RANGE),
        w_recency=log_uniform(WEIGHT_RANGE),
        ladder=ladder,
        min_pool_target=rng.randint(*MIN_POOL_TARGET_RANGE),
        pool_k=rng.randint(*POOL_K_RANGE),
    )


def config_hash(config: RetrievalConfig) -> str:
    canonical = json.dumps(asdict(config), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Trial:
    index: int  # 0 is always the hand-set config
    config: RetrievalConfig
    digest: str
    score: float  # mean pinball(log), refusals imputed at B1
    insufficient_rate: float
    coverage: float


@dataclass(frozen=True)
class SearchResult:
    trials: list[Trial]
    winner: Trial
    n_queries: int
    n_skipped: int
    seed: int


def select_winner(trials: list[Trial]) -> Trial:
    """Best eligible score; the hand-set config (trial 0) when nothing
    eligible beats it. Eligibility is relative to trial 0's refusal rate."""
    ceiling = trials[0].insufficient_rate + INSUFFICIENT_TOLERANCE
    eligible = [
        t
        for t in trials
        if t.insufficient_rate <= ceiling and COVERAGE_BAND[0] <= t.coverage <= COVERAGE_BAND[1]
    ]
    if not eligible:
        return trials[0]
    return min(eligible, key=lambda t: (t.score, t.index))


@dataclass
class _Accumulator:
    pinball_sum: float = 0.0
    insufficient: int = 0
    covered: int = 0
    scored: int = 0


def _eval_queries(store: DataStore) -> tuple[list[EvalQuery], int]:
    queries: list[EvalQuery] = []
    skipped = 0
    for row in eval_rows(store.transitions.comps_universe, VALIDATION_SEASONS).iter_rows(
        named=True
    ):
        built = build_eval_query(row, store.seasons)
        if isinstance(built, SkippedQuery):
            skipped += 1
        else:
            queries.append(built)
    return queries, skipped


def run_search(
    store: DataStore,
    n_configs: int = N_CONFIGS_DEFAULT,
    seed: int = SEED_DEFAULT,
    log: bool = False,
) -> SearchResult:
    """Query-major loop: one candidate precompute per query, scored under
    every config, so memory stays flat and term values are computed once."""
    rng = random.Random(seed)
    configs = [DEFAULT_RETRIEVAL] + [sample_config(rng) for _ in range(n_configs)]
    universe = store.transitions.comps_universe
    strengths = store.seasons.strength_frame()
    season_min = store.build_info.season_min

    queries, n_skipped = _eval_queries(store)
    accumulators = [_Accumulator() for _ in configs]
    for i, built in enumerate(queries):
        cands = candidate_set(built, universe, strengths, season_min)
        for accumulator, config in zip(accumulators, configs, strict=True):
            quantiles = score_query(cands, config)
            if quantiles is None:
                accumulator.pinball_sum += cands.fallback_pinball
                accumulator.insufficient += 1
            else:
                accumulator.pinball_sum += pinball_log_scalar(cands.actual_log, quantiles)
                if quantiles[0] <= cands.actual_multiplier <= quantiles[2]:
                    accumulator.covered += 1
                accumulator.scored += 1
        if log and (i + 1) % 500 == 0:
            print(f"  scored {i + 1}/{len(queries)} queries x {len(configs)} configs")

    trials = [
        Trial(
            index=index,
            config=config,
            digest=config_hash(config),
            score=acc.pinball_sum / len(queries),
            insufficient_rate=acc.insufficient / len(queries),
            coverage=acc.covered / acc.scored if acc.scored else 0.0,
        )
        for index, (config, acc) in enumerate(zip(configs, accumulators, strict=True))
    ]
    return SearchResult(
        trials=trials,
        winner=select_winner(trials),
        n_queries=len(queries),
        n_skipped=n_skipped,
        seed=seed,
    )


def runtime_parity_failures(
    store: DataStore, sample_size: int = 50, n_configs: int = 2, seed: int = SEED_DEFAULT + 1
) -> list[str]:
    """Belt-and-braces on real data: the numpy scorer must reproduce the real
    service's quantiles (and refusals) on a deterministic query sample."""
    rng = random.Random(seed)
    configs = [DEFAULT_RETRIEVAL] + [sample_config(rng) for _ in range(n_configs)]
    universe = store.transitions.comps_universe
    strengths = store.seasons.strength_frame()
    season_min = store.build_info.season_min
    queries, _ = _eval_queries(store)
    if not queries:
        return ["no validation queries to check"]
    stride = max(1, len(queries) // sample_size)
    failures: list[str] = []
    for built in queries[::stride][:sample_size]:
        cands = candidate_set(built, universe, strengths, season_min)
        universe_t = available_universe(universe, built.transfer_date)
        for k, config in enumerate(configs):
            result = find_comps(
                built.query,
                built.dest_league,
                built.dest_club,
                universe_t,
                strengths,
                season_min,
                config=config,
            )
            value_range, _ = summarize_pool(
                result.pool, built.query.value_eur, result.quality.relaxation_level
            )
            real = (
                None
                if value_range is None
                else (
                    value_range.q25_multiplier,
                    value_range.q50_multiplier,
                    value_range.q75_multiplier,
                )
            )
            fast = score_query(cands, config)
            label = f"player {built.player_id} @ {built.transfer_date} config {k}"
            if (real is None) != (fast is None):
                failures.append(f"{label}: refusal mismatch (real={real}, numpy={fast})")
            elif real is not None and fast is not None:
                drift = max(abs(r - f) for r, f in zip(real, fast, strict=True))
                if drift > PARITY_TOLERANCE:
                    failures.append(f"{label}: quantile drift {drift:.2e}")
    return failures


def render_constants_snippet(result: SearchResult, n_configs: int) -> str:
    """The exact constants.py replacement block for the reviewed freeze
    commit - pipeline code never writes into app/."""
    config = result.winner.config
    steps = ",\n".join(
        f"    LadderStep({step.label!r}, {step.age_band!r}, {step.value_bracket!r}, "
        f"{step.origin_tier_band!r}" + (", drop_club_terms=True)" if step.drop_club_terms else ")")
        for step in config.ladder
    )
    weights = "\n".join(
        f"{name} = {value!r}"
        for name, value in (
            ("W_LOG_VALUE", config.w_log_value),
            ("W_AGE", config.w_age),
            ("W_DEST_STRENGTH", config.w_dest_strength),
            ("W_ORIGIN_STRENGTH", config.w_origin_strength),
            ("W_ELO", config.w_elo),
            ("W_DEST_TERCILE", config.w_dest_tercile),
            ("W_ORIGIN_TERCILE", config.w_origin_tercile),
            ("W_MINUTES", config.w_minutes),
            ("W_SUB_POSITION", config.w_sub_position),
            ("W_RECENCY", config.w_recency),
        )
    )
    return (
        f"# Tuned by the temporal backtest: random search, {n_configs} configs, "
        f"seed {result.seed},\n"
        f"# scored on validation seasons {VALIDATION_SEASONS} (mean log pinball, "
        f"refusals imputed at B1).\n"
        f"# Winning config hash: {result.winner.digest}. "
        f"Reproduce: uv run python -m pipeline.eval tune\n"
        f"MIN_POOL_TARGET = {config.min_pool_target}\n\n"
        f"LADDER: tuple[LadderStep, ...] = (\n{steps},\n)\n\n"
        f"{weights}\n\n"
        f"POOL_K = {config.pool_k}\n"
    )
