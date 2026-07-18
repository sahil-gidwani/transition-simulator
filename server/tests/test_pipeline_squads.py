from datetime import date, timedelta

import polars as pl
from factories import make_clubs, make_competitions, make_games, make_valuations

from pipeline.transforms.common import club_league_by_season
from pipeline.transforms.squads import assemble_club_seasons, squad_values


def _no_games_leagues() -> pl.DataFrame:
    return club_league_by_season(make_games([]))


def test_valuation_on_july_first_belongs_to_that_season() -> None:
    vals = make_valuations(
        [
            {"player_id": 1, "date": date(2020, 7, 1), "market_value_in_eur": 5},
            {"player_id": 2, "date": date(2020, 7, 2), "market_value_in_eur": 7},
        ]
    )
    out = squad_values(vals, [2020, 2021])
    s2020 = out.filter(pl.col("season") == 2020)
    assert s2020.height == 1
    assert s2020["squad_value_eur"].item() == 5
    assert s2020["n_valued_players"].item() == 1
    # July 2 valuation belongs to the NEXT season's squad; the July 1 row is
    # exactly 365 days old at the 2021 start and still counts (inclusive cap).
    s2021 = out.filter(pl.col("season") == 2021)
    assert s2021["squad_value_eur"].item() == 12
    assert s2021["n_valued_players"].item() == 2


def test_staleness_cap_inclusive_at_365_days_exclusive_at_366() -> None:
    start = date(2020, 7, 1)
    vals = make_valuations(
        [
            {"player_id": 1, "date": start - timedelta(days=365), "market_value_in_eur": 3},
            {"player_id": 2, "date": start - timedelta(days=366), "market_value_in_eur": 9},
        ]
    )
    out = squad_values(vals, [2020])
    assert out.height == 1
    row = out.row(0, named=True)
    assert row["squad_value_eur"] == 3
    assert row["n_valued_players"] == 1


def test_player_who_moved_counts_once_at_latest_club() -> None:
    vals = make_valuations(
        [
            {"player_id": 1, "date": date(2020, 1, 1), "market_value_in_eur": 3},
            {
                "player_id": 1,
                "date": date(2020, 6, 1),
                "market_value_in_eur": 4,
                "current_club_id": 20,
            },
        ]
    )
    out = squad_values(vals, [2020])
    assert out.height == 1
    row = out.row(0, named=True)
    assert row["club_id"] == 20
    assert row["squad_value_eur"] == 4
    assert row["n_valued_players"] == 1


def test_two_players_same_club_sum_and_count() -> None:
    vals = make_valuations(
        [
            {"player_id": 1, "date": date(2020, 6, 1), "market_value_in_eur": 3_000_000},
            {"player_id": 2, "date": date(2020, 6, 1), "market_value_in_eur": 7_000_000},
        ]
    )
    out = squad_values(vals, [2020])
    assert out.height == 1
    row = out.row(0, named=True)
    assert row["squad_value_eur"] == 10_000_000
    assert row["n_valued_players"] == 2
    assert out["squad_value_eur"].dtype == pl.Int64


def test_terciles_split_seven_clubs_three_two_two() -> None:
    clubs = make_clubs([{"club_id": i, "name": f"Club {i}"} for i in range(1, 8)])
    comps = make_competitions([{}])
    vals = make_valuations(
        [
            {
                "player_id": i,
                "current_club_id": i,
                "market_value_in_eur": (8 - i) * 1_000_000,
                "date": date(2020, 6, 1),
            }
            for i in range(1, 8)
        ]
    )
    out = assemble_club_seasons(
        squad_values(vals, [2020]), _no_games_leagues(), clubs, comps, min_clubs=1
    )
    assert out.columns == [
        "club_id",
        "season",
        "club_name",
        "league",
        "league_source",
        "squad_value_eur",
        "n_valued_players",
        "tercile",
        "club_value_pct",
    ]
    # Output is sorted by club_id, and club i has the i-th highest squad value.
    assert out["club_id"].to_list() == [1, 2, 3, 4, 5, 6, 7]
    assert out["tercile"].to_list() == [1, 1, 1, 2, 2, 3, 3]
    assert out["tercile"].dtype == pl.Int8


def test_squad_value_tie_ranks_lower_club_id_first() -> None:
    clubs = make_clubs([{"club_id": i, "name": f"Club {i}"} for i in (10, 20, 30)])
    comps = make_competitions([{}])
    vals = make_valuations(
        [
            {"player_id": 1, "current_club_id": 10, "market_value_in_eur": 5_000_000},
            {"player_id": 2, "current_club_id": 20, "market_value_in_eur": 5_000_000},
            {"player_id": 3, "current_club_id": 30, "market_value_in_eur": 1_000_000},
        ]
    )
    out = assemble_club_seasons(
        squad_values(vals, [2020]), _no_games_leagues(), clubs, comps, min_clubs=1
    )
    by_club = {row["club_id"]: row["tercile"] for row in out.iter_rows(named=True)}
    assert by_club == {10: 1, 20: 2, 30: 3}


def test_club_value_pct_is_within_league_percentile_top_is_one() -> None:
    clubs = make_clubs([{"club_id": i, "name": f"Club {i}"} for i in (1, 2, 3, 4, 5)])
    comps = make_competitions([{}])
    vals = make_valuations(
        [
            {
                "player_id": i,
                "current_club_id": i,
                "market_value_in_eur": i * 1_000_000,
                "date": date(2020, 6, 1),
            }
            for i in (1, 2, 3, 4, 5)
        ]
    )
    out = assemble_club_seasons(
        squad_values(vals, [2020]), _no_games_leagues(), clubs, comps, min_clubs=1
    )
    # Sorted by club_id; club 5 is the richest -> 1.0, club 1 the poorest -> 0.0.
    assert out["club_value_pct"].to_list() == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert out["club_value_pct"].dtype == pl.Float32


def test_club_value_pct_null_for_single_member_league() -> None:
    clubs = make_clubs([{"club_id": 1, "name": "Solo FC"}])
    comps = make_competitions([{}])
    vals = make_valuations([{"player_id": 1, "current_club_id": 1, "date": date(2020, 6, 1)}])
    out = assemble_club_seasons(
        squad_values(vals, [2020]), _no_games_leagues(), clubs, comps, min_clubs=1
    )
    # (rank-1)/(n-1) is undefined at n=1; a percentile of a one-club league
    # carries no information either way.
    assert out["club_value_pct"].to_list() == [None]
    assert out["tercile"].to_list() == [1]


def test_terciles_null_below_min_clubs_floor() -> None:
    clubs = make_clubs([{"club_id": i, "name": f"Club {i}"} for i in (1, 2, 3)])
    comps = make_competitions([{}])
    vals = make_valuations(
        [
            {
                "player_id": i,
                "current_club_id": i,
                "market_value_in_eur": i * 1_000_000,
                "date": date(2020, 6, 1),
            }
            for i in (1, 2, 3)
        ]
    )
    squads = squad_values(vals, [2020])
    below = assemble_club_seasons(squads, _no_games_leagues(), clubs, comps, min_clubs=4)
    assert below["tercile"].to_list() == [None, None, None]
    assert below["league"].to_list() == ["AA1", "AA1", "AA1"]  # membership itself survives
    at_floor = assemble_club_seasons(squads, _no_games_leagues(), clubs, comps, min_clubs=3)
    assert at_floor["tercile"].to_list() == [3, 2, 1]


def test_snapshot_only_member_of_games_covered_league_is_unassigned() -> None:
    clubs = make_clubs(
        [
            {"club_id": 10, "name": "Club 10", "domestic_competition_id": "AA1"},
            {"club_id": 20, "name": "Club 20", "domestic_competition_id": "AA1"},
        ]
    )
    comps = make_competitions([{"competition_id": "AA1"}])
    # AA1 has games-derived membership in 2020 (club 10 played there), so the
    # snapshot may not pad it: club 20, with no games that season, is not a
    # member of anything - today's snapshot league is not evidence for 2020.
    games = make_games(
        [{"competition_id": "AA1", "season": 2020, "home_club_id": 10, "away_club_id": 99}]
    )
    vals = make_valuations(
        [
            {"player_id": 1, "current_club_id": 10, "date": date(2020, 6, 1)},
            {"player_id": 2, "current_club_id": 20, "date": date(2020, 6, 1)},
        ]
    )
    out = assemble_club_seasons(
        squad_values(vals, [2020]), club_league_by_season(games), clubs, comps
    )
    rows = {row["club_id"]: row for row in out.iter_rows(named=True)}
    assert rows[10]["league"] == "AA1"
    assert rows[10]["league_source"] == "games"
    assert rows[20]["league"] is None
    assert rows[20]["league_source"] == "none"
    assert rows[20]["tercile"] is None
    assert rows[20]["squad_value_eur"] is not None  # the row itself survives


def test_games_league_preferred_snapshot_fallback() -> None:
    clubs = make_clubs(
        [
            {"club_id": 10, "name": "Club 10", "domestic_competition_id": "AA1"},
            {"club_id": 20, "name": "Club 20", "domestic_competition_id": "AA1"},
        ]
    )
    comps = make_competitions([{"competition_id": "AA1"}, {"competition_id": "BB1"}])
    # Club 10 actually played in BB1 that season; club 20 has no games rows.
    games = make_games(
        [{"competition_id": "BB1", "season": 2020, "home_club_id": 10, "away_club_id": 99}]
    )
    vals = make_valuations(
        [
            {"player_id": 1, "current_club_id": 10, "date": date(2020, 6, 1)},
            {"player_id": 2, "current_club_id": 20, "date": date(2020, 6, 1)},
        ]
    )
    out = assemble_club_seasons(
        squad_values(vals, [2020]), club_league_by_season(games), clubs, comps
    )
    rows = {row["club_id"]: row for row in out.iter_rows(named=True)}
    assert rows[10]["league"] == "BB1"
    assert rows[10]["league_source"] == "games"
    assert rows[10]["club_name"] == "Club 10"
    assert rows[20]["league"] == "AA1"
    assert rows[20]["league_source"] == "snapshot"
