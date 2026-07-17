"""GET /api/destinations contract + destination resolution."""

from __future__ import annotations

import pytest
from api_factories import make_client, make_club_seasons, make_league_seasons, make_store

from app.core.errors import ApiError
from app.services.destinations import resolve_destination


def _store() -> object:
    return make_store(
        league_seasons=make_league_seasons(
            [
                {
                    "league": "AA1",
                    "tier": 1,
                    "strength": 18.0,
                    "league_name": "premier-league",
                    "country": "England",
                },
                {
                    "league": "BB1",
                    "tier": 1,
                    "strength": 19.0,
                    "league_name": "bundesliga",
                    "country": "Germany",
                },
                {
                    "league": "CC1",
                    "tier": 2,
                    "strength": 15.0,
                    "league_name": None,
                    "country": None,
                },
                {"league": "AA1", "season": 2024, "tier": 2},  # stale season: excluded
            ]
        ),
        club_seasons=make_club_seasons(
            [
                {"club_id": 10, "club_name": "Zeta FC", "league": "AA1", "tercile": 1},
                {
                    "club_id": 11,
                    "club_name": "Alpha FC",
                    "league": "AA1",
                    "tercile": 3,
                    "elo": None,
                    "elo_pct": None,
                    "elo_date": None,
                    "elo_mapped": False,
                },
                {"club_id": 20, "club_name": "Beta SV", "league": "BB1"},
                {"club_id": 12, "club_name": "Old FC", "league": "AA1", "season": 2024},
            ]
        ),
    )


def test_destinations_serve_latest_season_sorted() -> None:
    body = make_client(_store()).get("/api/destinations").json()

    assert body["season"] == 2025
    # Tier asc, then strength desc: BB1 (19.0) before AA1 (18.0), CC1 last.
    assert [lg["league_id"] for lg in body["leagues"]] == ["BB1", "AA1", "CC1"]
    aa1 = body["leagues"][1]
    assert aa1["name"] == "Premier League"
    assert aa1["country"] == "England"
    assert aa1["tier"] == 1
    # Clubs sorted by name; the 2024 row is gone.
    assert [c["name"] for c in aa1["clubs"]] == ["Alpha FC", "Zeta FC"]
    alpha, zeta = aa1["clubs"]
    assert alpha == {"club_id": 11, "name": "Alpha FC", "tercile": 3, "elo_available": False}
    assert zeta["elo_available"] is True


def test_null_strength_league_sorts_last_within_its_tier() -> None:
    # strength is nullable by the artifact contract (non-positive median squad
    # value); an unknown-strength league must never top its tier.
    store = make_store(
        league_seasons=make_league_seasons(
            [
                {"league": "AA1", "tier": 1, "strength": 18.0},
                {"league": "NN1", "tier": 1, "strength": None},
                {"league": "BB1", "tier": 1, "strength": 19.0},
            ]
        ),
    )
    body = make_client(store).get("/api/destinations").json()
    assert [lg["league_id"] for lg in body["leagues"]] == ["BB1", "AA1", "NN1"]


def test_league_without_slug_falls_back_to_code() -> None:
    body = make_client(_store()).get("/api/destinations").json()
    cc1 = next(lg for lg in body["leagues"] if lg["league_id"] == "CC1")
    assert cc1["name"] == "CC1"
    assert cc1["country"] is None


def test_resolve_destination_league_only() -> None:
    league, club = resolve_destination("AA1", None, _store())  # type: ignore[arg-type]
    assert league.league == "AA1"
    assert club is None


def test_resolve_destination_with_club() -> None:
    league, club = resolve_destination("AA1", 11, _store())  # type: ignore[arg-type]
    assert league.tier == 1
    assert club is not None
    assert club.club_name == "Alpha FC"


def test_resolve_destination_unknown_league_raises_404() -> None:
    with pytest.raises(ApiError) as excinfo:
        resolve_destination("XX9", None, _store())  # type: ignore[arg-type]
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "destination_not_found"


def test_resolve_destination_club_from_other_league_raises_404() -> None:
    with pytest.raises(ApiError) as excinfo:
        resolve_destination("AA1", 20, _store())  # type: ignore[arg-type]
    assert excinfo.value.status_code == 404
