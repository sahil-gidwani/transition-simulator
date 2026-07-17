"""Prediction-record frame builder: schema and nullability."""

from __future__ import annotations

import polars as pl
from eval_factories import make_record as _record

from pipeline.eval.records import RECORDS_SCHEMA, records_frame


def test_records_frame_matches_the_schema() -> None:
    frame = records_frame([_record()])
    assert frame.schema == pl.Schema(RECORDS_SCHEMA)
    assert frame.height == 1
    assert frame["q50"].to_list() == [1.1]
    assert frame["pool_multipliers"].to_list() == [[0.9, 1.1, 1.3]]


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
