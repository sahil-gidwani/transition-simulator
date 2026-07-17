"""Profile stats rules: per-90 math, GK clean-sheet attribution, peer percentiles."""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl
import pytest
from factories import make_appearances, make_club_games, make_games, make_players

from pipeline.transforms.profile import assemble_profile_stats, gk_stats, player_season_stats

_KEYS = ["player_id", "season", "league"]


def _games(n: int) -> pl.DataFrame:
    return make_games([{"game_id": 100 + i, "date": date(2020, 8, 1 + i)} for i in range(n)])


def _full_season_apps(player_id: int, n_games: int, **overrides: Any) -> list[dict[str, Any]]:
    return [
        {"game_id": 100 + i, "player_id": player_id, "minutes_played": 90, **overrides}
        for i in range(n_games)
    ]


def _one(frame: pl.DataFrame, player_id: int) -> dict[str, Any]:
    rows = frame.filter(pl.col("player_id") == player_id).to_dicts()
    assert len(rows) == 1
    return rows[0]


def test_per90_rates_hand_checked() -> None:
    apps = make_appearances(_full_season_apps(1, 5, goals=1, assists=0, yellow_cards=1))
    stats = player_season_stats(apps, _games(5))
    row = _one(stats, 1)
    assert (row["games_played"], row["minutes"], row["goals"]) == (5, 450, 5)
    assert row["goals_p90"] == 1.0  # 5 goals in 450 minutes
    assert row["assists_p90"] == 0.0
    assert row["ga_p90"] == 1.0
    assert row["cards_p90"] == 1.0


def test_non_domestic_games_excluded() -> None:
    games = pl.concat([_games(1), make_games([{"game_id": 200, "competition_type": "cup"}])])
    apps = make_appearances(
        [
            {"game_id": 100, "player_id": 1, "minutes_played": 90, "goals": 1},
            {"game_id": 200, "player_id": 1, "minutes_played": 90, "goals": 5},
        ]
    )
    row = _one(player_season_stats(apps, games), 1)
    assert (row["games_played"], row["goals"]) == (1, 1)


def test_zero_minutes_gives_null_per90() -> None:
    apps = make_appearances([{"game_id": 100, "player_id": 1, "minutes_played": 0}])
    row = _one(player_season_stats(apps, _games(1)), 1)
    assert row["games_played"] == 1
    assert row["goals_p90"] is None
    assert row["assists_p90"] is None
    assert row["ga_p90"] is None
    assert row["cards_p90"] is None


def _gk_fixture(minutes_by_game: dict[int, int], conceded_by_game: dict[int, int]) -> pl.DataFrame:
    apps = make_appearances(
        [
            {"game_id": g, "player_id": 5, "player_club_id": 10, "minutes_played": m}
            for g, m in minutes_by_game.items()
        ]
    )
    club_games = make_club_games(
        [{"game_id": g, "club_id": 10, "opponent_goals": c} for g, c in conceded_by_game.items()]
    )
    return gk_stats(apps, _games(len(minutes_by_game)), club_games)


def test_clean_sheet_requires_full_90_minutes() -> None:
    row = _one(_gk_fixture({100: 90, 101: 89}, {100: 0, 101: 0}), 5)
    # both games conceded 0, but only the full-90 appearance earns a clean sheet
    assert (row["full_games"], row["clean_sheets"]) == (1, 1)


def test_conceded_p90_hand_checked() -> None:
    row = _one(_gk_fixture({100: 90, 101: 90, 102: 90}, {100: 0, 101: 1, 102: 2}), 5)
    assert row["conceded"] == 3
    assert row["conceded_p90"] == 1.0  # 3 conceded in 270 minutes


def test_clean_sheet_rate_excludes_partial_appearances_from_both_sides() -> None:
    # 45-minute shutout is neither a clean sheet nor a full game
    row = _one(_gk_fixture({100: 90, 101: 90, 102: 45}, {100: 0, 101: 2, 102: 0}), 5)
    assert (row["full_games"], row["clean_sheets"]) == (2, 1)
    assert row["clean_sheet_rate"] == 0.5


def test_gk_rate_null_when_no_full_games() -> None:
    row = _one(_gk_fixture({100: 89}, {100: 0}), 5)
    assert row["full_games"] == 0
    assert row["clean_sheet_rate"] is None


def _assembled(
    apps: pl.DataFrame,
    games: pl.DataFrame,
    club_games: pl.DataFrame,
    players: pl.DataFrame,
    anchors_share: pl.DataFrame | None = None,
) -> pl.DataFrame:
    stats = player_season_stats(apps, games)
    gk = gk_stats(apps, games, club_games)
    return assemble_profile_stats(stats, gk, players, anchors_share)


def test_non_gk_rows_get_null_gk_stats_even_when_joinable() -> None:
    apps = make_appearances(
        _full_season_apps(1, 5, player_club_id=10) + _full_season_apps(5, 5, player_club_id=10)
    )
    club_games = make_club_games([{"game_id": 100 + i, "club_id": 10} for i in range(5)])
    players = make_players(
        [
            {"player_id": 1, "sub_position": "Centre-Forward", "position": "Attack"},
            {"player_id": 5, "sub_position": "Goalkeeper", "position": "Goalkeeper"},
        ]
    )
    out = _assembled(apps, _games(5), club_games, players)
    striker, keeper = _one(out, 1), _one(out, 5)
    assert striker["conceded_p90"] is None
    assert striker["clean_sheet_rate"] is None
    assert keeper["conceded_p90"] is not None
    assert keeper["clean_sheet_rate"] is not None


def _percentile_fixture() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    # players 1-3 above the 450-minute floor with goals_p90 = 0.0 / 1.0 / 2.0;
    # player 4 sits at 449 minutes with an inflated scoring rate.
    apps = make_appearances(
        _full_season_apps(1, 5, goals=0)
        + _full_season_apps(2, 5, goals=1)
        + _full_season_apps(3, 5, goals=2)
        + _full_season_apps(4, 4, goals=5)
        + [{"game_id": 104, "player_id": 4, "minutes_played": 89, "goals": 5}]
    )
    players = make_players([{"player_id": p} for p in (1, 2, 3, 4)])
    return apps, _games(5), make_club_games([]), players


def test_percentiles_hand_checked_on_three_player_peer_group() -> None:
    out = _assembled(*_percentile_fixture())
    assert [_one(out, p)["pct_goals_p90"] for p in (1, 2, 3)] == [0.0, 0.5, 1.0]


def test_below_floor_row_keeps_raw_stats_but_gets_null_pct_and_peer_n() -> None:
    out = _assembled(*_percentile_fixture())
    row = _one(out, 4)
    assert row["minutes"] == 449
    assert row["goals_p90"] == pytest.approx(25 * 90 / 449)  # raw stats survive the floor
    assert row["pct_goals_p90"] is None
    assert row["peer_n"] == 3  # the pool it would rank against
    assert out.schema["peer_n"] == pl.Int16


def test_below_floor_players_excluded_from_peer_pool() -> None:
    # player 4's huge goals_p90 must not push player 3 off the top percentile
    out = _assembled(*_percentile_fixture())
    assert _one(out, 3)["pct_goals_p90"] == 1.0
    assert out["peer_n"].to_list() == [3, 3, 3, 3]


def test_peer_group_of_one_gets_null_pct() -> None:
    apps = make_appearances(_full_season_apps(1, 5, goals=1))
    out = _assembled(apps, _games(5), make_club_games([]), make_players([{"player_id": 1}]))
    row = _one(out, 1)
    assert row["peer_n"] == 1
    assert row["pct_goals_p90"] is None


def test_minutes_share_column_joined_when_provided_else_null() -> None:
    apps = make_appearances(_full_season_apps(1, 5))
    games, club_games = _games(5), make_club_games([])
    players = make_players([{"player_id": 1}])
    without = _assembled(apps, games, club_games, players)
    assert without["minutes_share"].to_list() == [None]
    share = pl.DataFrame(
        [{"player_id": 1, "season": 2020, "league": "AA1", "minutes_share": 0.75}],
        schema={
            "player_id": pl.Int64,
            "season": pl.Int64,
            "league": pl.String,
            "minutes_share": pl.Float64,
        },
    )
    with_share = _assembled(apps, games, club_games, players, share)
    assert with_share["minutes_share"].to_list() == [0.75]


def test_profile_minutes_share_per_league_season() -> None:
    from factories import make_transfers

    from pipeline.transforms.minutes import covered_league_games
    from pipeline.transforms.profile import profile_minutes_share

    games = _games(2)  # two covered games for club 10 in league AA1, season 2020
    apps = make_appearances(
        [
            {"game_id": 100, "player_id": 1, "minutes_played": 90},
            {"game_id": 101, "player_id": 1, "minutes_played": 45},
        ]
    )
    covered = covered_league_games(games, apps)
    out = profile_minutes_share(apps, games, make_transfers([]), covered)
    row = out.row(0, named=True)
    assert (row["player_id"], row["season"], row["league"]) == (1, 2020, "AA1")
    assert row["minutes_share"] == pytest.approx(135 / 180)
