"""POST /api/simulations contract: happy paths, error paths, insufficient precedent."""

from __future__ import annotations

from typing import Any

from api_factories import (
    make_client,
    make_club_seasons,
    make_league_seasons,
    make_players_processed,
    make_profile_stats,
    make_store,
    make_transitions,
)
from fastapi.testclient import TestClient


def _full_store() -> Any:
    players = make_players_processed(
        [
            {"player_id": 1, "name": "Sim Target"},
            {
                "player_id": 2,
                "name": "No Value Man",
                "market_value_eur": None,
                "market_value_asof": None,
            },
            {
                "player_id": 3,
                "name": "Lone Keeper",
                "position_group": "GK",
                "sub_position": "Goalkeeper",
            },
        ]
    )
    league_seasons = make_league_seasons(
        [
            {
                "league": "AA1",
                "season": season,
                "tier": 1,
                "strength": 18.0,
                "league_name": "alpha-league",
                "country": "Alphaland",
            }
            for season in (2023, 2024, 2025)
        ]
        + [
            {
                "league": "BB1",
                "season": season,
                "tier": 1,
                "strength": 18.2,
                "league_name": "beta-league",
                "country": "Betaland",
            }
            for season in (2023, 2024, 2025)
        ]
    )
    club_seasons = make_club_seasons(
        [
            {"club_id": 10, "club_name": "Alpha FC", "league": "AA1", "tercile": 1},
            {
                "club_id": 21,
                "club_name": "Beta United",
                "league": "BB1",
                "tercile": 1,
                "elo_pct": 0.9,
            },
            {
                "club_id": 22,
                "club_name": "Beta Blanks",
                "league": "BB1",
                "tercile": 3,
                "elo": None,
                "elo_pct": None,
                "elo_date": None,
                "elo_mapped": False,
            },
        ]
    )
    transitions = make_transitions(
        [
            {
                "player_id": 100,
                "player_name": "Riser One",
                "v_before": 9_000_000,
                "multiplier": 1.4,
                "delta_pct": 0.4,
                "v_after": 12_600_000,
            },
            {
                "player_id": 101,
                "player_name": "Riser Two",
                "v_before": 11_000_000,
                "multiplier": 1.2,
                "delta_pct": 0.2,
                "v_after": 13_200_000,
            },
            {
                "player_id": 102,
                "player_name": "Faller One",
                "v_before": 10_000_000,
                "multiplier": 0.7,
                "delta_pct": -0.3,
                "v_after": 7_000_000,
            },
            {
                "player_id": 103,
                "player_name": "Flat One",
                "v_before": 12_000_000,
                "multiplier": 1.0,
                "delta_pct": 0.0,
                "v_after": 12_000_000,
            },
        ]
    )
    return make_store(
        players=players,
        league_seasons=league_seasons,
        club_seasons=club_seasons,
        transitions=transitions,
        profile_stats=make_profile_stats([{"player_id": 1, "minutes_share": 0.8}]),
    )


def _post(client: TestClient, player_id: int, league_id: str, club_id: int | None = None) -> Any:
    destination: dict[str, Any] = {"league_id": league_id}
    if club_id is not None:
        destination["club_id"] = club_id
    return client.post(
        "/api/simulations", json={"player_id": player_id, "destination": destination}
    )


def test_league_only_simulation_returns_range_comps_and_narrative() -> None:
    response = _post(make_client(_full_store()), 1, "BB1")

    assert response.status_code == 200
    body = response.json()
    assert body["player"]["name"] == "Sim Target"
    assert body["player"]["market_value_eur"] == 10_000_000
    assert body["destination"] == {
        "league_id": "BB1",
        "league_name": "Beta League",
        "country": "Betaland",
        "tier": 1,
        "club_id": None,
        "club_name": None,
        "club_tercile": None,
    }
    assert body["insufficient_precedent"] is False
    prediction = body["prediction"]
    assert prediction["horizon_months"] == 12
    assert prediction["low_eur"] <= prediction["mid_eur"] <= prediction["high_eur"]
    assert body["confidence"] in ("high", "medium", "low")
    assert body["pool_quality"]["pool_size"] == 4
    assert body["pool_quality"]["club_selected"] is False
    assert body["shown_comps"] == 6
    # Comps arrive most-similar first and include the decliner, shown honestly.
    similarities = [c["similarity"] for c in body["comps"]]
    assert similarities == sorted(similarities, reverse=True)
    assert any(c["delta_pct"] < 0 for c in body["comps"])
    assert body["narrative"]


def test_simulation_with_club_activates_club_context() -> None:
    response = _post(make_client(_full_store()), 1, "BB1", club_id=21)

    assert response.status_code == 200
    body = response.json()
    assert body["destination"]["club_name"] == "Beta United"
    assert body["destination"]["club_tercile"] == 1
    assert body["pool_quality"]["club_selected"] is True
    assert body["pool_quality"]["dest_elo_available"] is True
    assert body["pool_quality"]["elo_pool_coverage"] == 1.0


def test_unknown_player_is_404() -> None:
    response = _post(make_client(_full_store()), 999, "BB1")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "player_not_found"


def test_unknown_league_is_404() -> None:
    response = _post(make_client(_full_store()), 1, "XX9")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "destination_not_found"


def test_club_outside_the_league_is_404() -> None:
    response = _post(make_client(_full_store()), 1, "AA1", club_id=21)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "destination_not_found"


def test_player_without_value_is_409() -> None:
    response = _post(make_client(_full_store()), 2, "BB1")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "player_without_value"
    assert "No Value Man" in body["error"]["message"]


def test_no_precedent_yields_insufficient_with_no_range() -> None:
    # A goalkeeper with zero GK transitions anywhere in the universe.
    response = _post(make_client(_full_store()), 3, "BB1")

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_precedent"] is True
    assert body["prediction"] is None
    assert body["confidence"] == "insufficient"
    assert body["comps"] == []
    assert body["pool_quality"]["expanded_search"] is True
    assert "Insufficient precedent" in body["narrative"]
    assert "€" not in body["narrative"]


def test_malformed_body_uses_the_error_schema() -> None:
    client = make_client(_full_store())
    response = client.post("/api/simulations", json={"player_id": 1})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["detail"]
