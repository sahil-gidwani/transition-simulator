"""Synthetic backtest-record builder shared by the eval test modules."""

from __future__ import annotations

from datetime import date
from typing import Any

from pipeline.eval.records import PredictionRecord

_DEFAULTS: dict[str, Any] = {
    "player_id": 1,
    "transfer_date": date(2022, 7, 1),
    "season": 2022,
    "v_before": 10_000_000,
    "v_after": 12_000_000,
    "actual_multiplier": 1.2,
    "q25": 0.9,
    "q50": 1.1,
    "q75": 1.3,
    "insufficient": False,
    "pool_size": 24,
    "relaxation_level": 0,
    "confidence": "high",
    "iqr_log": 0.2,
    "n_available": 5_000,
    "b1_q25": None,
    "b1_q50": None,
    "b1_q75": None,
    "b2_q25": None,
    "b2_q50": None,
    "b2_q75": None,
    "b2_fallback": True,
    "age_at_transfer": 25.0,
    "position_group": "ATT",
    "from_tier": 1,
    "to_tier": 1,
    "minutes_known": True,
    "pool_multipliers": [0.9, 1.1, 1.3],
    "pool_similarities": [1.0, 0.9, 0.8],
}


def make_record(**overrides: Any) -> PredictionRecord:
    return PredictionRecord(**{**_DEFAULTS, **overrides})
