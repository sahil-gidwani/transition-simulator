from datetime import date, timedelta
from typing import Any

from factories import make_transfers

from pipeline.transforms.loans import LoanCounts, flag_suspected_loans


def _round_trip(
    player_id: int,
    out_date: date,
    ret_date: date,
    fee_out: float | None,
    fee_ret: float | None,
) -> list[dict[str, Any]]:
    return [
        {
            "player_id": player_id,
            "transfer_date": out_date,
            "from_club_id": 10,
            "to_club_id": 20,
            "transfer_fee": fee_out,
        },
        {
            "player_id": player_id,
            "transfer_date": ret_date,
            "from_club_id": 20,
            "to_club_id": 10,
            "transfer_fee": fee_ret,
        },
    ]


def test_zero_fee_round_trip_flags_both_legs() -> None:
    tf = make_transfers(_round_trip(1, date(2020, 7, 1), date(2021, 1, 17), 0.0, 0.0))
    out, counts = flag_suspected_loans(tf)
    assert out["suspected_loan"].to_list() == [True, True]
    assert counts == LoanCounts(loan_pairs=1, buyback_pairs=0, ambiguous_pairs=0, rows_flagged=2)


def test_buyback_round_trip_kept_and_counted() -> None:
    tf = make_transfers(_round_trip(1, date(2020, 7, 1), date(2021, 1, 17), 0.0, 5_000_000.0))
    out, counts = flag_suspected_loans(tf)
    assert out["suspected_loan"].to_list() == [False, False]
    assert counts == LoanCounts(loan_pairs=0, buyback_pairs=1, ambiguous_pairs=0, rows_flagged=0)


def test_gap_at_548_days_flags_but_549_does_not() -> None:
    start = date(2020, 1, 1)
    tf = make_transfers(
        _round_trip(1, start, start + timedelta(days=548), 0.0, 0.0)
        + _round_trip(2, start, start + timedelta(days=549), 0.0, 0.0)
    )
    out, counts = flag_suspected_loans(tf)
    assert out["suspected_loan"].to_list() == [True, True, False, False]
    assert counts.loan_pairs == 1
    assert counts.rows_flagged == 2


def test_null_fee_round_trip_is_ambiguous_and_kept() -> None:
    tf = make_transfers(_round_trip(1, date(2020, 7, 1), date(2021, 1, 17), None, None))
    out, counts = flag_suspected_loans(tf)
    assert out["suspected_loan"].to_list() == [False, False]
    assert counts == LoanCounts(loan_pairs=0, buyback_pairs=0, ambiguous_pairs=1, rows_flagged=0)


def test_greedy_pairing_interleaved_round_trips() -> None:
    # Legs: A->B (row 0), B->A (row 1), A->B (row 2), B->A (row 3).
    # Candidate pairs by gap: (2,3)=30d, (0,1)=31d, (1,2)=304d, (0,3)=365d.
    # Greedy 1:1 keeps each out leg and each return leg once: (0,3) drops
    # because out leg 0 already paired at its shorter 31d gap.
    tf = make_transfers(
        [
            {"player_id": 1, "transfer_date": date(2020, 7, 1), "transfer_fee": 0.0},
            {
                "player_id": 1,
                "transfer_date": date(2020, 8, 1),
                "from_club_id": 20,
                "to_club_id": 10,
                "transfer_fee": 0.0,
            },
            {"player_id": 1, "transfer_date": date(2021, 6, 1), "transfer_fee": 0.0},
            {
                "player_id": 1,
                "transfer_date": date(2021, 7, 1),
                "from_club_id": 20,
                "to_club_id": 10,
                "transfer_fee": 0.0,
            },
        ]
    )
    out, counts = flag_suspected_loans(tf)
    assert counts.loan_pairs == 3
    assert counts.rows_flagged == 4
    assert out["suspected_loan"].to_list() == [True, True, True, True]


def test_return_leg_pairs_with_closest_out_leg() -> None:
    # Two A->B out legs compete for one B->A return: the 61d gap wins over
    # the 213d gap, so the earlier out leg stays unflagged.
    tf = make_transfers(
        [
            {"player_id": 1, "transfer_date": date(2020, 1, 1), "transfer_fee": 0.0},
            {"player_id": 1, "transfer_date": date(2020, 6, 1), "transfer_fee": 0.0},
            {
                "player_id": 1,
                "transfer_date": date(2020, 8, 1),
                "from_club_id": 20,
                "to_club_id": 10,
                "transfer_fee": 0.0,
            },
        ]
    )
    out, counts = flag_suspected_loans(tf)
    assert out["suspected_loan"].to_list() == [False, True, True]
    assert counts == LoanCounts(loan_pairs=1, buyback_pairs=0, ambiguous_pairs=0, rows_flagged=2)


def test_fee_null_single_legs_never_flagged() -> None:
    tf = make_transfers(
        [
            {"player_id": 1, "transfer_date": date(2020, 7, 1), "transfer_fee": None},
            {"player_id": 2, "transfer_date": date(2020, 7, 1), "transfer_fee": None},
        ]
    )
    out, counts = flag_suspected_loans(tf)
    assert out["suspected_loan"].to_list() == [False, False]
    assert counts == LoanCounts(loan_pairs=0, buyback_pairs=0, ambiguous_pairs=0, rows_flagged=0)
