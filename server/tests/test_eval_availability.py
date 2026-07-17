"""The backtest's date-exact availability rule (its one leakage gate)."""

from __future__ import annotations

from datetime import date

from api_factories import make_transitions

from pipeline.eval.availability import available_universe


def test_v_after_date_on_the_query_date_is_usable() -> None:
    universe = make_transitions([{"player_id": 100, "v_after_date": date(2024, 7, 1)}])
    result = available_universe(universe, date(2024, 7, 1))
    assert result["player_id"].to_list() == [100]


def test_v_after_date_one_day_later_is_not_usable() -> None:
    universe = make_transitions([{"player_id": 100, "v_after_date": date(2024, 7, 2)}])
    result = available_universe(universe, date(2024, 7, 1))
    assert result.is_empty()


def test_the_query_row_never_informs_itself() -> None:
    # A query at its own transfer date: v_after_date is >= t + 180d by
    # construction, so the row must drop out of its own comp universe.
    t = date(2023, 7, 1)
    universe = make_transitions(
        [
            {"player_id": 1, "transfer_date": t, "v_after_date": date(2024, 7, 1)},
            {"player_id": 2, "transfer_date": date(2021, 8, 1), "v_after_date": date(2022, 8, 1)},
        ]
    )
    result = available_universe(universe, t)
    assert result["player_id"].to_list() == [2]


def test_pre_history_date_returns_an_empty_frame() -> None:
    universe = make_transitions([{"v_after_date": date(2015, 1, 1)}])
    assert available_universe(universe, date(2012, 7, 1)).is_empty()


def test_columns_and_dtypes_pass_through_unchanged() -> None:
    universe = make_transitions([{"v_after_date": date(2020, 1, 1)}])
    result = available_universe(universe, date(2024, 1, 1))
    assert result.schema == universe.schema
