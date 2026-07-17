"""Metric formulas: pinball, coverage, width, MdAPE, segments, suppression."""

from __future__ import annotations

import math
from typing import Any

import pytest
from eval_factories import make_record as _record

from pipeline.eval.metrics import add_segments, age_band_label, aggregate
from pipeline.eval.records import PredictionRecord, records_frame

E = math.e


def _pooled(records: list[PredictionRecord], **kwargs: Any) -> dict[str, Any]:
    return aggregate(records_frame(records), [], **kwargs).row(0, named=True)


# --- pinball ------------------------------------------------------------------


def test_pinball_undershoot_hand_computed() -> None:
    # actual = e (ln = 1), every quantile = 1.0 (ln = 0): diff = +1, so the
    # log pinball at tau is exactly tau.
    row = _pooled([_record(actual_multiplier=E, q25=1.0, q50=1.0, q75=1.0)])
    assert row["pinball_25"] == pytest.approx(0.25)
    assert row["pinball_50"] == pytest.approx(0.50)
    assert row["pinball_75"] == pytest.approx(0.75)
    assert row["pinball_mean"] == pytest.approx(0.50)


def test_pinball_overshoot_hand_computed() -> None:
    # actual = 1.0 (ln = 0), every quantile = e (ln = 1): diff = -1, so the
    # log pinball at tau is exactly 1 - tau.
    row = _pooled([_record(actual_multiplier=1.0, q25=E, q50=E, q75=E)])
    assert row["pinball_25"] == pytest.approx(0.75)
    assert row["pinball_50"] == pytest.approx(0.50)
    assert row["pinball_75"] == pytest.approx(0.25)


def test_pinball_raw_is_on_the_multiplier_scale() -> None:
    row = _pooled([_record(actual_multiplier=E, q25=1.0, q50=1.0, q75=1.0)])
    assert row["pinball_raw_mean"] == pytest.approx(0.5 * (E - 1.0))


# --- coverage / width / mdape ----------------------------------------------------


def test_coverage_counts_endpoint_ties_as_covered() -> None:
    records = [
        _record(actual_multiplier=1.2, q25=1.2, q75=1.5),  # tie on q25
        _record(actual_multiplier=1.5, q25=1.2, q75=1.5),  # tie on q75
        _record(actual_multiplier=1.6, q25=1.2, q75=1.5),  # outside
    ]
    assert _pooled(records)["coverage"] == pytest.approx(2 / 3)


def test_width_is_the_log_quantile_gap() -> None:
    row = _pooled([_record(q25=1.0, q75=E)])
    assert row["width_mean"] == pytest.approx(1.0)
    assert row["width_median"] == pytest.approx(1.0)


def test_mdape_of_the_median() -> None:
    records = [
        _record(actual_multiplier=1.0, q50=1.1),  # ape 0.1
        _record(actual_multiplier=1.0, q50=1.3),  # ape 0.3
        _record(actual_multiplier=2.0, q50=1.0),  # ape 0.5
    ]
    assert _pooled(records)["mdape"] == pytest.approx(0.3)


# --- refusals ---------------------------------------------------------------------


def test_insufficient_rows_are_counted_but_never_scored() -> None:
    records = [
        _record(actual_multiplier=1.2, q25=1.0, q50=1.2, q75=1.4),
        _record(
            q25=None, q50=None, q75=None, iqr_log=None, insufficient=True, actual_multiplier=9.0
        ),
    ]
    row = _pooled(records)
    assert row["n_total"] == 2
    assert row["n_scored"] == 1
    assert row["insufficient_rate"] == pytest.approx(0.5)
    assert row["coverage"] == pytest.approx(1.0)  # the refused outlier can't dilute it


def test_baseline_columns_score_through_the_same_aggregator() -> None:
    records = [_record(q25=None, q50=None, q75=None, b1_q25=1.0, b1_q50=1.2, b1_q75=1.4)]
    precedent = _pooled(records)
    baseline = _pooled(records, q25="b1_q25", q50="b1_q50", q75="b1_q75")
    assert precedent["n_scored"] == 0
    assert baseline["n_scored"] == 1
    assert baseline["coverage"] == pytest.approx(1.0)


# --- segments ---------------------------------------------------------------------


def test_age_bands_are_half_open() -> None:
    assert age_band_label(None) is None
    assert age_band_label(21.99) == "<22"
    assert age_band_label(22.0) == "22-25"
    assert age_band_label(25.99) == "22-25"
    assert age_band_label(26.0) == "26-29"
    assert age_band_label(30.0) == "30+"


def test_add_segments_labels_match_the_python_side() -> None:
    frame = records_frame(
        [
            _record(age_at_transfer=21.5, v_before=999_999, from_tier=2, to_tier=1),
            _record(age_at_transfer=None, v_before=1_000_000, from_tier=1, to_tier=2),
            _record(age_at_transfer=30.0, v_before=15_000_000, from_tier=None, to_tier=1),
            _record(age_at_transfer=25.0, v_before=5_000_000, from_tier=1, to_tier=1),
        ]
    )
    segmented = add_segments(frame)
    assert segmented["age_band"].to_list() == ["<22", None, "30+", "22-25"]
    assert segmented["value_bracket"].to_list() == ["<1M", "1-5M", ">=15M", "5-15M"]
    assert segmented["tier_jump"].to_list() == ["up", "down", "unknown", "same"]


# --- cells -----------------------------------------------------------------------


def test_small_cells_are_flagged_not_dropped() -> None:
    records = [_record(position_group="ATT") for _ in range(3)] + [_record(position_group="GK")]
    cells = aggregate(records_frame(records), ["position_group"], min_cell=2)
    by_group = {row["position_group"]: row for row in cells.iter_rows(named=True)}
    assert by_group["ATT"]["suppressed"] is False
    assert by_group["GK"]["suppressed"] is True
    assert cells["position_group"].to_list() == ["ATT", "GK"]  # most-populated first
