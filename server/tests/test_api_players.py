"""GET /api/players/{id} contract: bio, value history, 404."""

from __future__ import annotations

from datetime import date

from api_factories import (
    make_client,
    make_league_seasons,
    make_player_values,
    make_players_processed,
    make_store,
    make_transitions,
)


def test_profile_returns_bio_and_sorted_value_history() -> None:
    store = make_store(
        players=make_players_processed([{"player_id": 1, "name": "History Man"}]),
        player_values=make_player_values(
            [
                {"player_id": 1, "date": date(2026, 6, 1), "market_value_eur": 12_000_000},
                {"player_id": 1, "date": date(2024, 6, 1), "market_value_eur": 6_000_000},
                {"player_id": 2, "date": date(2026, 6, 1), "market_value_eur": 99_000_000},
            ]
        ),
        league_seasons=make_league_seasons(
            [{"league": "AA1", "league_name": "premier-league", "tier": 2}]
        ),
    )
    response = make_client(store).get("/api/players/1")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "History Man"
    assert body["age"] == 28  # born 1998-06-15, FixedClock 2026-07-17
    assert body["club_name"] == "Alpha FC"
    assert body["league_name"] == "Premier League"
    assert body["league_tier"] == 2
    assert body["market_value_eur"] == 10_000_000
    assert body["market_value_asof"] == "2026-06-01"
    assert body["value_history"] == [
        {"date": "2024-06-01", "value_eur": 6_000_000},
        {"date": "2026-06-01", "value_eur": 12_000_000},
    ]


def test_profile_with_no_valuation_serves_null_value_and_null_asof() -> None:
    store = make_store(
        players=make_players_processed(
            [
                {
                    "player_id": 1,
                    "market_value_eur": None,
                    "market_value_asof": None,
                    "date_of_birth": None,
                }
            ]
        ),
    )
    body = make_client(store).get("/api/players/1").json()
    assert body["market_value_eur"] is None
    assert body["market_value_asof"] is None
    assert body["age"] is None
    assert body["league_name"] is None  # league missing from latest season entirely
    assert body["value_history"] == []


def test_profile_unknown_player_is_404_with_error_schema() -> None:
    store = make_store(players=make_players_processed([{"player_id": 1}]))
    response = make_client(store).get("/api/players/999")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "player_not_found"
    assert "999" in body["error"]["message"]


def test_profile_lists_the_players_own_qualifying_transfers() -> None:
    store = make_store(
        players=make_players_processed([{"player_id": 1, "name": "Mover Man"}]),
        transitions=make_transitions(
            [
                {
                    "player_id": 1,
                    "transfer_date": date(2021, 7, 1),
                    "season": 2021,
                    "from_club_name": "First FC",
                    "to_club_name": "Second FC",
                },
                {
                    "player_id": 1,
                    "transfer_date": date(2024, 1, 15),
                    "season": 2023,
                    "from_club_name": "Second FC",
                    "to_club_name": "Third FC",
                },
                # A loan leg never annotates the chart.
                {
                    "player_id": 1,
                    "transfer_date": date(2022, 7, 1),
                    "season": 2022,
                    "suspected_loan": True,
                },
                {"player_id": 2, "transfer_date": date(2023, 7, 1)},
            ]
        ),
        league_seasons=make_league_seasons([{"league": "AA1"}]),
    )
    body = make_client(store).get("/api/players/1").json()
    assert body["transfers"] == [
        {"date": "2021-07-01", "from_club": "First FC", "to_club": "Second FC"},
        {"date": "2024-01-15", "from_club": "Second FC", "to_club": "Third FC"},
    ]
