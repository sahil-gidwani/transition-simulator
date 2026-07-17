"""Minutes-share rules: covered denominators, transfer splits, exact window edges."""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl
from factories import make_appearances, make_games, make_transfers

from pipeline.transforms.minutes import (
    covered_league_games,
    minutes_share,
    played_minutes,
    player_segments,
    possible_minutes,
)

_ANCHOR_DEFAULTS: dict[str, Any] = {
    "anchor_id": 1,
    "player_id": 1,
    "window_start": date(2020, 7, 1),
    "window_end": date(2021, 7, 1),
    "base_club_id": 10,
}
_ANCHOR_SCHEMA: dict[str, type[pl.DataType]] = {
    "anchor_id": pl.Int64,
    "player_id": pl.Int64,
    "window_start": pl.Date,
    "window_end": pl.Date,
    "base_club_id": pl.Int64,
}


def _anchors(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame([{**_ANCHOR_DEFAULTS, **row} for row in rows], schema=_ANCHOR_SCHEMA)


def _share(
    anchors: pl.DataFrame, transfers: pl.DataFrame, games: pl.DataFrame, apps: pl.DataFrame
) -> list[float | None]:
    covered = covered_league_games(games, apps)
    return minutes_share(anchors, transfers, covered, apps, ["AA1"])["minutes_share"].to_list()


def test_full_participation_gives_share_one() -> None:
    games = make_games(
        [{"game_id": 100 + i, "date": date(2020, 8, 1 + i), "home_club_id": 10} for i in range(10)]
    )
    apps = make_appearances(
        [
            {"game_id": 100 + i, "player_id": 1, "date": date(2020, 8, 1 + i), "minutes_played": 90}
            for i in range(10)
        ]
    )
    assert _share(_anchors([{}]), make_transfers([]), games, apps) == [1.0]


def test_games_without_appearance_rows_drop_from_denominator() -> None:
    # 4 covered games at club 10; 3 more have zero appearance rows -> not playable time.
    games = make_games(
        [{"game_id": 100 + i, "date": date(2020, 8, 1 + i), "home_club_id": 10} for i in range(7)]
    )
    apps = make_appearances(
        # player 1 plays 2 games; games 102-103 covered only via another player
        [
            {"game_id": 100 + i, "player_id": 1, "date": date(2020, 8, 1 + i), "minutes_played": 90}
            for i in range(2)
        ]
        + [
            {"game_id": 102 + i, "player_id": 2, "date": date(2020, 8, 3 + i), "minutes_played": 90}
            for i in range(2)
        ]
    )
    # denominator is 4 covered games (360), not 7 (630): share 0.5, not 180/630
    assert _share(_anchors([{}]), make_transfers([]), games, apps) == [0.5]


def test_mid_window_transfer_splits_denominator() -> None:
    transfers = make_transfers(
        [{"player_id": 1, "transfer_date": date(2021, 1, 1), "from_club_id": 10, "to_club_id": 20}]
    )
    # away_club_id pinned to an uninvolved club: coverage rows exist for both sides
    games = make_games(
        [
            {"game_id": 100, "date": date(2020, 8, 1), "home_club_id": 10, "away_club_id": 30},
            {"game_id": 101, "date": date(2021, 2, 1), "home_club_id": 10, "away_club_id": 30},
            {"game_id": 102, "date": date(2020, 9, 1), "home_club_id": 20, "away_club_id": 30},
            {"game_id": 103, "date": date(2021, 3, 1), "home_club_id": 20, "away_club_id": 30},
        ]
    )
    # counts: 100 (from-club, pre-boundary) and 103 (to-club, post-boundary) only
    apps = make_appearances(
        [
            {"game_id": g, "player_id": p, "date": d, "player_club_id": c, "minutes_played": 90}
            for g, p, d, c in [
                (100, 1, date(2020, 8, 1), 10),
                (101, 3, date(2021, 2, 1), 10),
                (102, 3, date(2020, 9, 1), 20),
                (103, 1, date(2021, 3, 1), 20),
            ]
        ]
    )
    # base_club_id is deliberately wrong: the first segment club comes from the
    # boundary's from_club_id, not the anchor's base.
    anchors = _anchors([{"base_club_id": 99}])
    covered = covered_league_games(games, apps)
    segments = player_segments(anchors, transfers)
    assert segments.rows() == [
        (1, 10, date(2020, 7, 1), date(2021, 1, 1)),
        (1, 20, date(2021, 1, 1), date(2021, 7, 1)),
    ]
    assert possible_minutes(segments, covered)["possible_minutes"].to_list() == [180]
    assert _share(anchors, transfers, games, apps) == [1.0]


def test_zero_covered_games_yields_null_share() -> None:
    # the club's only game has zero appearance rows -> possible == 0 -> NULL, never 0.0
    games = make_games([{"game_id": 100, "date": date(2020, 8, 1), "home_club_id": 10}])
    apps = make_appearances([])
    assert _share(_anchors([{}]), make_transfers([]), games, apps) == [None]


def test_share_clipped_at_one() -> None:
    # 95 recorded minutes in one 90-minute covered game (stoppage time) -> clipped to 1.0
    games = make_games([{"game_id": 100, "date": date(2020, 8, 1), "home_club_id": 10}])
    apps = make_appearances(
        [{"game_id": 100, "player_id": 1, "date": date(2020, 8, 1), "minutes_played": 95}]
    )
    assert _share(_anchors([{}]), make_transfers([]), games, apps) == [1.0]


def test_segment_boundaries_are_start_inclusive_end_exclusive() -> None:
    transfers = make_transfers(
        [{"player_id": 1, "transfer_date": date(2021, 1, 1), "from_club_id": 10, "to_club_id": 20}]
    )
    games = make_games(
        [
            # comments give the edge each game sits on; away side pinned uninvolved
            {"game_id": 100, "date": date(2020, 7, 1), "home_club_id": 10, "away_club_id": 30},
            {"game_id": 101, "date": date(2021, 1, 1), "home_club_id": 10, "away_club_id": 30},
            {"game_id": 102, "date": date(2021, 1, 1), "home_club_id": 20, "away_club_id": 30},
            {"game_id": 103, "date": date(2021, 7, 1), "home_club_id": 20, "away_club_id": 30},
        ]
    )
    # 100 on window_start: in; 101 on seg_end: out; 102 on seg_start: in;
    # 103 on window_end: out
    apps = make_appearances(
        [{"game_id": 100 + i, "player_id": 2, "date": date(2020, 8, 1)} for i in range(4)]
    )
    segments = player_segments(_anchors([{}]), transfers)
    covered = covered_league_games(games, apps)
    assert possible_minutes(segments, covered)["possible_minutes"].to_list() == [180]


def test_appearance_on_window_end_excluded_from_numerator() -> None:
    apps = make_appearances(
        [
            {"game_id": 100, "player_id": 1, "date": date(2021, 6, 30), "minutes_played": 60},
            {"game_id": 101, "player_id": 1, "date": date(2021, 7, 1), "minutes_played": 90},
            # wrong competition: never counts even inside the window
            {
                "game_id": 102,
                "player_id": 1,
                "date": date(2021, 1, 1),
                "competition_id": "CUP",
                "minutes_played": 90,
            },
        ]
    )
    played = played_minutes(_anchors([{}]), apps, ["AA1"])
    assert played["played_minutes"].to_list() == [60]


def test_null_base_club_and_no_transfers_yields_null_share() -> None:
    games = make_games([{"game_id": 100, "date": date(2020, 8, 1), "home_club_id": 10}])
    apps = make_appearances([{"game_id": 100, "player_id": 2, "date": date(2020, 8, 1)}])
    anchors = _anchors([{"base_club_id": None}])
    segments = player_segments(anchors, make_transfers([]))
    assert segments["club_id"].to_list() == [None]
    assert _share(anchors, make_transfers([]), games, apps) == [None]
