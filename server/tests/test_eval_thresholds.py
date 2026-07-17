"""Confidence-tier honesty grid + validation-coverage calibration decision."""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest
from eval_factories import make_record

from app.services.valuation import _confidence
from pipeline.eval.records import PredictionRecord, records_frame
from pipeline.eval.thresholds import (
    CalibrationDecision,
    calibration_shifts,
    hand_set_thresholds,
    propose_conf_thresholds,
    render_thresholds_snippet,
    tier_expr,
    tier_stats,
)


def test_tier_expr_mirrors_the_serving_confidence_logic() -> None:
    cases = [
        {"pool_size": 16, "iqr_log": 0.2, "relaxation_level": 0},
        {"pool_size": 12, "iqr_log": 0.35, "relaxation_level": 0},  # exact high edges
        {"pool_size": 16, "iqr_log": 0.2, "relaxation_level": 1},  # relaxed out of high
        {"pool_size": 8, "iqr_log": 0.5, "relaxation_level": 2},
        {"pool_size": 4, "iqr_log": 0.2, "relaxation_level": 0},  # pool too small
        {"pool_size": 24, "iqr_log": 0.9, "relaxation_level": 0},  # too dispersed
    ]
    frame = records_frame([make_record(**case) for case in cases]).with_columns(
        tier=tier_expr(hand_set_thresholds())
    )
    expected = [
        _confidence(case["pool_size"], case["iqr_log"], case["relaxation_level"]) for case in cases
    ]
    assert frame["tier"].to_list() == expected


def test_insufficient_rows_get_their_own_tier_and_no_stats() -> None:
    records = records_frame(
        [
            make_record(),
            make_record(insufficient=True, q25=None, q50=None, q75=None, iqr_log=None),
        ]
    )
    assert records.with_columns(tier=tier_expr(hand_set_thresholds()))["tier"].to_list() == [
        "high",
        "insufficient",
    ]
    assert tier_stats(records, hand_set_thresholds())["n"].sum() == 1


def _honest_records() -> pl.DataFrame:
    # 240 tight rows (narrow, coverage 0.5) + 240 loose rows (wide, coverage 0.5).
    rows: list[PredictionRecord] = []
    for i in range(240):
        rows.append(
            make_record(
                pool_size=16,
                iqr_log=0.2,
                relaxation_level=0,
                q25=0.9,
                q75=1.1,
                actual_multiplier=1.0 if i % 2 == 0 else 1.5,
            )
        )
        rows.append(
            make_record(
                pool_size=7,
                iqr_log=0.55,
                relaxation_level=1,
                q25=0.7,
                q75=1.4,
                actual_multiplier=1.0 if i % 2 == 0 else 2.0,
            )
        )
    return records_frame(rows)


def test_propose_finds_an_honest_setting_when_one_exists() -> None:
    proposal = propose_conf_thresholds(_honest_records())
    assert proposal.thresholds is not None
    assert proposal.n_honest > 0
    stats = {row["tier"]: row for row in proposal.stats.iter_rows(named=True)}
    assert stats["high"]["n"] >= 100
    assert 0.45 <= stats["high"]["coverage"] <= 0.55
    assert stats["high"]["width_median"] < stats["medium"]["width_median"]


def test_propose_keeps_hand_set_when_nothing_is_honest() -> None:
    # Every range misses: no setting can reach the coverage band.
    records = records_frame(
        [make_record(actual_multiplier=9.0, pool_size=16, iqr_log=0.2) for _ in range(300)]
    )
    proposal = propose_conf_thresholds(records)
    assert proposal.thresholds is None
    assert proposal.n_honest == 0
    assert proposal.stats.height >= 1  # hand-set table still reported


def _uncovered_low_row(actual: float, **overrides: Any) -> PredictionRecord:
    # Pool quantiles at nominal levels: q25 = 0.7, q75 = 1.55 (equal weights).
    return make_record(
        pool_size=4,
        iqr_log=0.4,
        relaxation_level=0,
        pool_multipliers=[0.5, 0.9, 1.1, 2.0],
        pool_similarities=[1.0, 1.0, 1.0, 1.0],
        q25=0.7,
        q75=1.55,
        actual_multiplier=actual,
        **overrides,
    )


def test_no_calibration_inside_the_coverage_band() -> None:
    rows = [
        make_record(actual_multiplier=1.0 if i % 2 == 0 else 5.0, pool_size=4) for i in range(200)
    ]
    decision = calibration_shifts(records_frame(rows), hand_set_thresholds())
    assert decision.needed is False
    assert decision.shifts == {"high": 0.0, "medium": 0.0, "low": 0.0}
    assert decision.pooled_coverage == pytest.approx(0.5)


def test_calibration_widens_an_undercovered_tier_from_its_pools() -> None:
    # Half the actuals sit just below the nominal q25 (0.505 vs 0.7) and are
    # recovered at delta = 0.13, when the lower level reaches the pool's
    # bottom order statistic; the other half are never coverable.
    rows = [_uncovered_low_row(0.505 if i % 2 == 0 else 10.0) for i in range(120)]
    decision = calibration_shifts(records_frame(rows), hand_set_thresholds())
    assert decision.needed is True
    assert decision.shifts["low"] == pytest.approx(0.13)
    assert decision.shifts["high"] == 0.0
    assert decision.tier_coverage["low"] == pytest.approx(0.0)


def test_thin_tiers_are_never_calibrated() -> None:
    rows = [_uncovered_low_row(0.505 if i % 2 == 0 else 10.0) for i in range(50)]
    decision = calibration_shifts(records_frame(rows), hand_set_thresholds())
    assert decision.needed is True
    assert decision.shifts["low"] == 0.0  # n < 100: stays nominal, documented


def test_snippet_carries_every_frozen_constant() -> None:
    proposal = propose_conf_thresholds(_honest_records())
    decision = CalibrationDecision(
        needed=True,
        pooled_coverage=0.4,
        shifts={"high": 0.02, "medium": 0.05, "low": 0.0},
        tier_coverage={"high": 0.44},
    )
    snippet = render_thresholds_snippet(proposal, decision)
    for needle in (
        "CONF_HIGH_MIN_POOL",
        "CONF_HIGH_MAX_IQR_LOG",
        "CONF_HIGH_MAX_RELAXATION",
        "CONF_MED_MIN_POOL",
        "CONF_MED_MAX_IQR_LOG",
        "CONF_MED_MAX_RELAXATION",
        "CAL_SHIFT_HIGH = 0.02",
        "CAL_SHIFT_MEDIUM = 0.05",
        "CAL_SHIFT_LOW = 0.0",
    ):
        assert needle in snippet
