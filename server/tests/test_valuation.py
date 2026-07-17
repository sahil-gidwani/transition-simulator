"""Weighted quantiles, range math and confidence tiers."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.services.comps import ScoredComp
from app.services.valuation import summarize_pool, weighted_quantile


def _comp(multiplier: float, similarity: float = 1.0, **overrides: Any) -> ScoredComp:
    fields: dict[str, Any] = {
        "player_id": 100,
        "player_name": "Comp Player",
        "transfer_date": date(2023, 7, 1),
        "season": 2023,
        "age_at_transfer": 25.0,
        "sub_position": "Centre-Forward",
        "from_club_name": "Origin FC",
        "to_club_name": "Dest FC",
        "from_league": "AA1",
        "to_league": "BB1",
        "v_before": 10_000_000,
        "v_after": round(10_000_000 * multiplier),
        "multiplier": multiplier,
        "delta_pct": multiplier - 1.0,
        "distance": 0.1,
        "similarity": similarity,
        "tags": ["similar market value"],
        "elo_term_used": False,
    }
    fields.update(overrides)
    return ScoredComp(**fields)


# --- weighted_quantile -------------------------------------------------------------


def test_equal_weights_reduce_to_midpoint_quantiles() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    weights = [1.0, 1.0, 1.0, 1.0]
    assert weighted_quantile(values, weights, 0.5) == pytest.approx(2.5)
    assert weighted_quantile(values, weights, 0.25) == pytest.approx(1.5)
    assert weighted_quantile(values, weights, 0.75) == pytest.approx(3.5)


def test_two_points_clamp_at_the_ends() -> None:
    values = [1.0, 2.0]
    weights = [1.0, 1.0]
    assert weighted_quantile(values, weights, 0.25) == 1.0  # exactly at c_1
    assert weighted_quantile(values, weights, 0.5) == pytest.approx(1.5)
    assert weighted_quantile(values, weights, 0.75) == 2.0
    assert weighted_quantile(values, weights, 0.0) == 1.0
    assert weighted_quantile(values, weights, 1.0) == 2.0


def test_heavier_weight_pulls_the_median() -> None:
    # c = 0.375 and 0.875; Q(0.5) interpolates a quarter of the way up.
    assert weighted_quantile([1.0, 2.0], [3.0, 1.0], 0.5) == pytest.approx(1.25)


def test_unsorted_input_is_handled() -> None:
    assert weighted_quantile([4.0, 1.0, 3.0, 2.0], [1.0] * 4, 0.5) == pytest.approx(2.5)


def test_quantiles_are_monotone_in_q() -> None:
    values = [0.4, 0.9, 1.1, 1.3, 2.2]
    weights = [2.0, 0.5, 1.0, 3.0, 0.25]
    qs = [weighted_quantile(values, weights, q / 20) for q in range(21)]
    assert qs == sorted(qs)


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        weighted_quantile([], [], 0.5)
    with pytest.raises(ValueError, match="same length"):
        weighted_quantile([1.0], [1.0, 2.0], 0.5)
    with pytest.raises(ValueError, match="non-negative"):
        weighted_quantile([1.0, 2.0], [1.0, -1.0], 0.5)
    with pytest.raises(ValueError, match="positive"):
        weighted_quantile([1.0, 2.0], [0.0, 0.0], 0.5)


# --- summarize_pool ---------------------------------------------------------------


def test_fewer_than_two_comps_means_no_range() -> None:
    assert summarize_pool([], 10_000_000, 0) == (None, "insufficient")
    assert summarize_pool([_comp(1.2)], 10_000_000, 0) == (None, "insufficient")


def test_two_comps_produce_a_clamped_range() -> None:
    value_range, confidence = summarize_pool([_comp(0.8), _comp(1.2)], 10_000_000, 0)
    assert value_range is not None
    assert value_range.q25_eur == 8_000_000
    assert value_range.q75_eur == 12_000_000
    assert value_range.q50_eur == 10_000_000
    assert confidence == "low"  # pool of 2 is never better than low


def test_all_decliner_pool_lands_strictly_below_current_value() -> None:
    pool = [_comp(m) for m in (0.5, 0.6, 0.7, 0.8)]
    value_range, _ = summarize_pool(pool, 10_000_000, 0)
    assert value_range is not None
    assert value_range.q75_eur < 10_000_000
    assert value_range.q25_eur < value_range.q50_eur < value_range.q75_eur


def test_similarity_weights_shift_the_range() -> None:
    pool = [_comp(0.8, similarity=3.0), _comp(1.2, similarity=1.0)]
    value_range, _ = summarize_pool(pool, 10_000_000, 0)
    assert value_range is not None
    assert value_range.q50_multiplier == pytest.approx(0.9)  # pulled toward 0.8


def test_high_confidence_needs_big_tight_unrelaxed_pool() -> None:
    pool = [_comp(1.0 + i * 0.01) for i in range(12)]  # 12 comps, very tight
    _, confidence = summarize_pool(pool, 10_000_000, 0)
    assert confidence == "high"


def test_relaxation_caps_confidence() -> None:
    pool = [_comp(1.0 + i * 0.01) for i in range(12)]
    _, at_level_one = summarize_pool(pool, 10_000_000, 1)
    _, at_level_three = summarize_pool(pool, 10_000_000, 3)
    assert at_level_one == "medium"
    assert at_level_three == "low"


def test_wide_dispersion_caps_confidence() -> None:
    pool = [_comp(m) for m in (0.4, 0.6, 0.9, 1.1, 1.6, 2.4) for _ in range(2)]
    _, confidence = summarize_pool(pool, 10_000_000, 0)
    assert confidence == "low"


def test_medium_confidence_band() -> None:
    pool = [_comp(1.0 + i * 0.03) for i in range(7)]  # 7 comps, moderately tight
    _, confidence = summarize_pool(pool, 10_000_000, 0)
    assert confidence == "medium"
