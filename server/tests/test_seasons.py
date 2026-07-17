"""Season-exact SeasonsRepo accessors (the backtest's historical context)."""

from __future__ import annotations

from api_factories import make_club_seasons, make_league_seasons

from app.repositories.seasons import SeasonsRepo


def _repo() -> SeasonsRepo:
    return SeasonsRepo(
        make_league_seasons(
            [
                {"league": "AA1", "season": 2023, "tier": 2, "strength": 17.0},
                {"league": "AA1", "season": 2025, "tier": 1, "strength": 18.4},
                {"league": "BB1", "season": 2025, "tier": 1, "strength": 18.0},
            ]
        ),
        make_club_seasons(
            [
                {"club_id": 10, "season": 2023, "tercile": 3, "elo_pct": 0.25},
                {"club_id": 10, "season": 2025, "tercile": 1, "elo_pct": 0.75},
            ]
        ),
    )


def test_league_at_returns_the_requested_season_not_latest() -> None:
    league = _repo().league_at("AA1", 2023)
    assert league is not None
    assert (league.season, league.tier, league.strength) == (2023, 2, 17.0)


def test_league_at_misses_return_none() -> None:
    repo = _repo()
    assert repo.league_at("AA1", 2024) is None  # season gap
    assert repo.league_at("ZZ1", 2025) is None  # unknown league


def test_club_at_returns_the_requested_season_not_latest() -> None:
    club = _repo().club_at(10, 2023)
    assert club is not None
    assert (club.season, club.tercile, club.elo_pct) == (2023, 3, 0.25)


def test_club_at_misses_return_none() -> None:
    repo = _repo()
    assert repo.club_at(10, 2024) is None  # season gap
    assert repo.club_at(99, 2025) is None  # unknown club
