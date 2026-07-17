"""Prediction-record frame builder: schema and nullability."""

from __future__ import annotations

from datetime import date

import polars as pl

from pipeline.eval.records import RECORDS_SCHEMA, PredictionRecord, records_frame


def _record(**overrides: object) -> PredictionRecord:
    fields: dict[str, object] = {
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
        "b1_q25": 0.85,
        "b1_q50": 1.0,
        "b1_q75": 1.2,
        "b2_q25": 0.9,
        "b2_q50": 1.05,
        "b2_q75": 1.25,
        "b2_fallback": False,
        "age_at_transfer": 25.0,
        "position_group": "ATT",
        "from_tier": 1,
        "to_tier": 1,
        "minutes_known": True,
    }
    fields.update(overrides)
    return PredictionRecord(**fields)  # type: ignore[arg-type]


def test_records_frame_matches_the_schema() -> None:
    frame = records_frame([_record()])
    assert frame.schema == pl.Schema(RECORDS_SCHEMA)
    assert frame.height == 1
    assert frame["q50"].to_list() == [1.1]


def test_insufficient_records_carry_null_quantiles() -> None:
    frame = records_frame(
        [
            _record(),
            _record(
                q25=None,
                q50=None,
                q75=None,
                iqr_log=None,
                insufficient=True,
                confidence="insufficient",
                pool_size=1,
            ),
        ]
    )
    assert frame["q50"].null_count() == 1
    assert frame["insufficient"].to_list() == [False, True]
