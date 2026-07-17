"""Leakage-safe naive baselines: global and age x position quantiles."""

from __future__ import annotations

from typing import Any

import pytest
from api_factories import make_transitions

from pipeline.eval.baselines import compute_baselines


def _universe(rows: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    return make_transitions([{"player_id": 100 + i, **row} for i, row in enumerate(rows)])


def test_b1_is_the_global_empirical_quantiles() -> None:
    universe = _universe([{"multiplier": m} for m in (1.0, 2.0, 3.0, 4.0)])
    result = compute_baselines(universe, age=None, position_group="ATT")
    assert result.b1 == pytest.approx((1.75, 2.5, 3.25))
    assert result.b2 == result.b1  # null age: bucket undefined
    assert result.b2_fallback is True


def test_b2_uses_only_the_matching_age_and_position_bucket() -> None:
    bucket = [{"multiplier": float(m), "age_at_transfer": 23.0} for m in range(1, 21)]
    noise = [
        {"multiplier": 100.0, "age_at_transfer": 30.0},  # out of band
        {"multiplier": 200.0, "age_at_transfer": 26.0},  # boundary: 26 is the next band
        {"multiplier": 300.0, "age_at_transfer": 23.0, "position_group": "MID"},
    ]
    result = compute_baselines(_universe(bucket + noise), age=25.0, position_group="ATT")
    assert result.b2_fallback is False
    assert result.b2 == pytest.approx((5.75, 10.5, 15.25))
    assert result.b1 is not None
    assert result.b1[2] > 15.25  # sanity: the global set does include the noise


def test_b2_falls_back_to_b1_when_the_bucket_is_thin() -> None:
    bucket = [{"multiplier": float(m), "age_at_transfer": 23.0} for m in range(1, 20)]  # 19 rows
    result = compute_baselines(_universe(bucket), age=25.0, position_group="ATT")
    assert result.b2_fallback is True
    assert result.b2 == result.b1


def test_too_thin_a_universe_quotes_nothing() -> None:
    result = compute_baselines(_universe([{"multiplier": 1.5}]), age=25.0, position_group="ATT")
    assert result.b1 is None
    assert result.b2 is None
    assert result.b2_fallback is True
