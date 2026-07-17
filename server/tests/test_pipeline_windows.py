from datetime import date, timedelta

import polars as pl
import pytest
from factories import make_transfers, make_valuations

from pipeline.config import FunnelCounts
from pipeline.transforms.loans import flag_suspected_loans
from pipeline.transforms.transfers import CleaningCounts, annotate_scope, clean_transfers
from pipeline.transforms.windows import (
    attach_outcomes,
    attach_v_after,
    attach_v_before,
    compute_funnel,
    max_valuation_date,
)

T = date(2021, 7, 1)


def _run_chain(
    transfers: pl.DataFrame, valuations: pl.DataFrame, covered_ids: list[int]
) -> tuple[pl.DataFrame, CleaningCounts]:
    cleaned, counts = clean_transfers(transfers)
    tf = annotate_scope(cleaned, covered_ids)
    tf, _ = flag_suspected_loans(tf)
    tf = attach_v_before(tf, valuations)
    tf = attach_v_after(tf, valuations)
    tf = attach_outcomes(tf, max_valuation_date(valuations))
    return tf, counts


def test_v_before_window_boundaries() -> None:
    # Window is [t-180d, t-1d]: t-181d falls out, and the transfer day itself
    # is excluded (a valuation on t may already price the move).
    transfers = make_transfers([{"player_id": p, "transfer_date": T} for p in (1, 2, 3, 4)])
    valuations = make_valuations(
        [
            {"player_id": 1, "date": T - timedelta(days=180), "market_value_in_eur": 1_000_000},
            {"player_id": 2, "date": T - timedelta(days=181), "market_value_in_eur": 1_000_000},
            {"player_id": 3, "date": T - timedelta(days=1), "market_value_in_eur": 1_000_000},
            {"player_id": 4, "date": T, "market_value_in_eur": 1_000_000},
        ]
    )
    out, _ = _run_chain(transfers, valuations, [10, 20])
    assert out["v_before"].to_list() == [1_000_000, None, 1_000_000, None]
    assert out["v_before_date"].to_list() == [
        T - timedelta(days=180),
        None,
        T - timedelta(days=1),
        None,
    ]


def test_v_before_picks_latest_in_window() -> None:
    transfers = make_transfers([{"player_id": 1, "transfer_date": T}])
    valuations = make_valuations(
        [
            {"player_id": 1, "date": T - timedelta(days=100), "market_value_in_eur": 1_000_000},
            {"player_id": 1, "date": T - timedelta(days=50), "market_value_in_eur": 2_000_000},
        ]
    )
    out, _ = _run_chain(transfers, valuations, [10, 20])
    assert out["v_before"].to_list() == [2_000_000]
    assert out["v_before_date"].to_list() == [T - timedelta(days=50)]


def test_v_after_window_boundaries() -> None:
    # Window is [t+180d, t+540d], both edges inclusive.
    transfers = make_transfers([{"player_id": p, "transfer_date": T} for p in (1, 2, 3, 4)])
    valuations = make_valuations(
        [
            {"player_id": 1, "date": T + timedelta(days=180), "market_value_in_eur": 1_000_000},
            {"player_id": 2, "date": T + timedelta(days=179), "market_value_in_eur": 1_000_000},
            {"player_id": 3, "date": T + timedelta(days=540), "market_value_in_eur": 1_000_000},
            {"player_id": 4, "date": T + timedelta(days=541), "market_value_in_eur": 1_000_000},
        ]
    )
    out, _ = _run_chain(transfers, valuations, [10, 20])
    assert out["v_after"].to_list() == [1_000_000, None, 1_000_000, None]
    assert out["v_after_date"].to_list() == [
        T + timedelta(days=180),
        None,
        T + timedelta(days=540),
        None,
    ]


def test_v_after_picks_earliest_in_window() -> None:
    transfers = make_transfers([{"player_id": 1, "transfer_date": T}])
    valuations = make_valuations(
        [
            {"player_id": 1, "date": T + timedelta(days=200), "market_value_in_eur": 3_000_000},
            {"player_id": 1, "date": T + timedelta(days=300), "market_value_in_eur": 4_000_000},
        ]
    )
    out, _ = _run_chain(transfers, valuations, [10, 20])
    assert out["v_after"].to_list() == [3_000_000]
    assert out["v_after_date"].to_list() == [T + timedelta(days=200)]


def test_censored_flips_exactly_180d_before_history_end() -> None:
    history_end = date(2021, 12, 31)
    cutoff = history_end - timedelta(days=180)
    transfers = make_transfers(
        [
            {"player_id": 1, "transfer_date": cutoff},
            {"player_id": 2, "transfer_date": cutoff + timedelta(days=1)},
        ]
    )
    valuations = make_valuations([{"player_id": 9, "date": history_end}])
    out, _ = _run_chain(transfers, valuations, [10, 20])
    assert out["censored"].to_list() == [False, True]


def test_outcome_math_on_hand_computed_row() -> None:
    transfers = make_transfers([{"player_id": 1, "transfer_date": T}])
    valuations = make_valuations(
        [
            {"player_id": 1, "date": T - timedelta(days=30), "market_value_in_eur": 2_000_000},
            {"player_id": 1, "date": T + timedelta(days=400), "market_value_in_eur": 5_000_000},
        ]
    )
    out, _ = _run_chain(transfers, valuations, [10, 20])
    assert out["multiplier"].to_list() == [2.5]
    assert out["delta_pct"].to_list() == [1.5]
    assert out["days_to_after"].to_list() == [400]


def test_compute_funnel_counts_each_stage() -> None:
    # Hand-counted fixture: 8 raw rows -> 7 cleaned (one undated) -> 6 in
    # scope (player 2 leaves coverage) -> 5 with v_before (player 3 has no
    # history) -> 4 observable (player 4 censored) -> 3 with v_after (player
    # 5 has none in window) -> 1 non-loan (player 6's round trip drops).
    transfers = make_transfers(
        [
            {"player_id": 1, "transfer_date": date(2020, 7, 1)},
            {"player_id": 2, "transfer_date": date(2020, 7, 1), "to_club_id": 99},
            {"player_id": 3, "transfer_date": date(2020, 7, 1)},
            {"player_id": 4, "transfer_date": date(2021, 8, 1)},
            {"player_id": 5, "transfer_date": date(2020, 7, 1)},
            {"player_id": 6, "transfer_date": date(2020, 7, 1), "transfer_fee": 0.0},
            {
                "player_id": 6,
                "transfer_date": date(2021, 1, 17),
                "from_club_id": 20,
                "to_club_id": 10,
                "transfer_fee": 0.0,
            },
            {"player_id": 7, "transfer_date": None},
        ]
    )
    valuations = make_valuations(
        [
            {"player_id": 1, "date": date(2020, 6, 1), "market_value_in_eur": 2_000_000},
            {"player_id": 1, "date": date(2021, 7, 1), "market_value_in_eur": 5_000_000},
            # History ends 2021-12-31, so the censor cutoff is 2021-07-04.
            {"player_id": 2, "date": date(2021, 12, 31), "market_value_in_eur": 1_000_000},
            {"player_id": 4, "date": date(2021, 7, 15), "market_value_in_eur": 3_000_000},
            {"player_id": 5, "date": date(2020, 6, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 6, "date": date(2020, 6, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 6, "date": date(2020, 12, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 6, "date": date(2021, 3, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 6, "date": date(2021, 8, 1), "market_value_in_eur": 1_000_000},
        ]
    )
    out, cleaning = _run_chain(transfers, valuations, [10, 20])
    assert cleaning == CleaningCounts(
        raw=8, with_date=7, dupes_removed=0, self_transfers_removed=0, cleaned=7
    )
    assert compute_funnel(out, cleaning) == FunnelCounts(
        raw=8,
        cleaned=7,
        in_scope=6,
        with_v_before=5,
        observable=4,
        with_v_after=3,
        non_loan=1,
    )


def test_clean_transfers_dedup_keeps_first_after_sort() -> None:
    # Same (player, date) twice: after the documented sort the row with the
    # lower from_club_id comes first and is the one kept.
    transfers = make_transfers(
        [
            {"player_id": 1, "transfer_date": T, "from_club_id": 30, "to_club_id": 40},
            {"player_id": 1, "transfer_date": T, "from_club_id": 10, "to_club_id": 20},
        ]
    )
    cleaned, counts = clean_transfers(transfers)
    assert cleaned.height == 1
    assert cleaned["from_club_id"].to_list() == [10]
    assert counts.dupes_removed == 1


def test_clean_transfers_drops_self_transfers_keeps_null_club_ids() -> None:
    transfers = make_transfers(
        [
            {"player_id": 1, "transfer_date": T, "from_club_id": 10, "to_club_id": 10},
            {"player_id": 2, "transfer_date": T, "from_club_id": None},
            {"player_id": 3, "transfer_date": T, "to_club_id": None},
            {"player_id": 4, "transfer_date": T},
        ]
    )
    cleaned, counts = clean_transfers(transfers)
    assert cleaned["player_id"].to_list() == [2, 3, 4]
    assert counts == CleaningCounts(
        raw=4, with_date=4, dupes_removed=0, self_transfers_removed=1, cleaned=3
    )


def test_max_valuation_date_requires_dated_values() -> None:
    with pytest.raises(ValueError, match="no dated market values"):
        max_valuation_date(make_valuations([]))
    with pytest.raises(ValueError, match="no dated market values"):
        max_valuation_date(make_valuations([{"date": None}]))
