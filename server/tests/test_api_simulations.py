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


def _full_store(transitions_rows: list[dict[str, Any]] | None = None) -> Any:
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
        transitions_rows
        if transitions_rows is not None
        else [
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
            {
                "player_id": 104,
                "player_name": "Flat Two",
                "v_before": 9_500_000,
                "multiplier": 1.05,
                "delta_pct": 0.05,
                "v_after": 9_975_000,
            },
            {
                "player_id": 105,
                "player_name": "Riser Three",
                "v_before": 10_500_000,
                "multiplier": 1.1,
                "delta_pct": 0.1,
                "v_after": 11_550_000,
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
    assert body["direction"] in ("rise", "decline", "flat")  # served, never client-derived
    assert body["confidence"] in ("high", "medium", "low")
    assert body["pool_quality"]["pool_size"] == 6
    assert body["pool_quality"]["club_selected"] is False
    assert body["pool_quality"]["club_indistinct"] is False  # league-only: no club to judge
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
    # The club selection is judged against the league-only search; with this
    # tiny universe the midpoint barely moves.
    assert body["pool_quality"]["club_indistinct"] is True
    # Beta United sits at pct 0.9 while every comp went to a pct-0.5 club:
    # no precedent AT this standing, and the narrative says which cause.
    assert body["pool_quality"]["club_standing_support"] == 0
    assert "No comparable move on record went to a club of" in body["narrative"]


def test_club_indistinct_fires_even_when_the_pool_cap_reshuffles_membership() -> None:
    # Above POOL_K candidates the club terms reshuffle which comps make the
    # cap; the flag keys on midpoint drift alone, so an unmoved answer is
    # still flagged (a same-pool requirement would silently suppress this).
    from app.services.constants import POOL_K

    base: dict[str, Any] = {
        "multiplier": 1.1,
        "delta_pct": 0.1,
        "sub_position": "Second Striker",
        "to_club_value_pct": 0.9,
    }
    rows: list[dict[str, Any]] = [
        {
            **base,
            "player_id": 100 + i,
            "player_name": f"Bulk {i:02d}",
            "v_before": 10_000_000,
            "v_after": 11_000_000,
            "to_elo_pct": None,
        }
        for i in range(POOL_K)
    ] + [
        # Worse on value league-only (out of the cap), but an exact Elo match
        # for Beta United - the club terms pull these six into the pool.
        {
            **base,
            "player_id": 500 + i,
            "player_name": f"Elo Match {i}",
            "v_before": 14_000_000,
            "v_after": 15_400_000,
            "to_elo_pct": 0.9,
        }
        for i in range(6)
    ]
    client = make_client(_full_store(rows))
    league_only = _post(client, 1, "BB1").json()
    clubbed = _post(client, 1, "BB1", club_id=21).json()

    def pool_ids(body: Any) -> set[tuple[int, str]]:
        return {(c["player_id"], c["transfer_date"]) for c in body["comps"]}

    assert pool_ids(clubbed) != pool_ids(league_only)  # the cap genuinely reshuffled
    assert clubbed["prediction"]["mid_eur"] == league_only["prediction"]["mid_eur"]
    assert clubbed["pool_quality"]["club_indistinct"] is True
    # An indistinct pick must never outrank the league-only confidence.
    assert clubbed["confidence"] == league_only["confidence"]


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
    assert body["direction"] is None  # no range, no direction claim
    assert body["confidence"] == "insufficient"
    assert body["comps"] == []
    assert body["pool_quality"]["expanded_search"] is True
    assert "Insufficient precedent" in body["narrative"]
    assert "€" not in body["narrative"]


def test_prediction_is_the_weighted_quantile_of_exactly_the_returned_comps() -> None:
    # Principle 1, end to end: with more matches than POOL_K, the served range
    # must be recomputable from precisely the comps in the response - never
    # from the pre-cap universe or a truncated subset.
    from app.services.constants import POOL_K
    from app.services.valuation import weighted_quantile

    rows = [
        {
            "player_id": 100 + i,
            "player_name": f"Comp {i:02d}",
            "v_before": 8_000_000 + i * 300_000,
            "multiplier": 0.6 + i * 0.05,
            "delta_pct": 0.6 + i * 0.05 - 1.0,
            "v_after": round((8_000_000 + i * 300_000) * (0.6 + i * 0.05)),
        }
        for i in range(POOL_K + 6)
    ]
    response = _post(make_client(_full_store(rows)), 1, "BB1")

    assert response.status_code == 200
    body = response.json()
    comps = body["comps"]
    assert body["pool_quality"]["pool_size"] == POOL_K
    assert len(comps) == POOL_K
    multipliers = [c["multiplier"] for c in comps]
    similarities = [c["similarity"] for c in comps]
    value = body["player"]["market_value_eur"]
    prediction = body["prediction"]
    assert prediction["low_eur"] == round(
        value * weighted_quantile(multipliers, similarities, 0.25)
    )
    assert prediction["mid_eur"] == round(
        value * weighted_quantile(multipliers, similarities, 0.50)
    )
    assert prediction["high_eur"] == round(
        value * weighted_quantile(multipliers, similarities, 0.75)
    )


def test_max_relaxation_with_two_comps_still_produces_an_honest_range() -> None:
    # Both comps qualify only once the origin filter drops (last ladder level).
    rows: list[dict[str, Any]] = [
        {
            "player_id": 100 + i,
            "from_tier": None,
            "from_league": None,
            "from_tercile": None,
            "multiplier": 0.9 + i * 0.2,
            "delta_pct": 0.9 + i * 0.2 - 1.0,
            "v_after": round(10_000_000 * (0.9 + i * 0.2)),
        }
        for i in range(2)
    ]
    response = _post(make_client(_full_store(rows)), 1, "BB1", club_id=21)

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_precedent"] is False
    assert body["prediction"] is not None
    assert body["confidence"] == "low"
    quality = body["pool_quality"]
    assert quality["relaxation_level"] == 5
    assert "origin league filter dropped" in quality["relaxation_steps"][-1]
    assert "destination league band widened" in quality["relaxation_steps"][-1]
    assert quality["expanded_search"] is True
    # Club terms are ignored at this level even though the club has a rating.
    assert quality["dest_elo_available"] is True
    assert quality["elo_pool_coverage"] == 0.0
    assert all(c["from_league"] is None for c in body["comps"])  # serializes cleanly


def test_single_comp_is_insufficient_but_names_the_evidence() -> None:
    rows = [{"player_id": 100, "player_name": "Only Match"}]
    response = _post(make_client(_full_store(rows)), 1, "BB1")

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_precedent"] is True
    assert body["prediction"] is None
    assert body["confidence"] == "insufficient"
    assert [c["player_name"] for c in body["comps"]] == ["Only Match"]
    assert "Only Match" in body["narrative"]
    assert "no responsible value range" in body["narrative"]


def test_malformed_body_uses_the_error_schema() -> None:
    client = make_client(_full_store())
    response = client.post("/api/simulations", json={"player_id": 1})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["detail"]
