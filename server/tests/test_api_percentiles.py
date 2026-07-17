"""GET /api/players/{id}/percentiles contract: metric sets, direction, floor."""

from __future__ import annotations

from typing import Any

from api_factories import make_client, make_players_processed, make_profile_stats, make_store


def _client(profile_rows: list[dict[str, Any]], player_row: dict[str, Any] | None = None) -> Any:
    store = make_store(
        players=make_players_processed([player_row or {"player_id": 1}]),
        profile_stats=make_profile_stats(profile_rows),
    )
    return make_client(store)


def test_outfielder_gets_outfield_metrics_with_inverted_cards() -> None:
    client = _client([{"player_id": 1, "pct_goals_p90": 0.8, "pct_cards_p90": 0.9, "peer_n": 40}])
    body = client.get("/api/players/1/percentiles").json()

    assert body["has_stats"] is True
    assert body["season"] == 2025
    assert body["league_id"] == "AA1"
    assert body["below_floor"] is False
    by_metric = {m["metric"]: m for m in body["metrics"]}
    assert set(by_metric) == {"goals_p90", "assists_p90", "ga_p90", "cards_p90"}
    assert by_metric["goals_p90"]["percentile"] == 80
    assert by_metric["goals_p90"]["direction"] == "higher_better"
    # Raw 0.9 = cards higher than 90% of peers -> served as 10th percentile.
    assert by_metric["cards_p90"]["percentile"] == 10
    assert by_metric["cards_p90"]["direction"] == "lower_better"
    assert all(m["peer_n"] == 40 for m in body["metrics"])


def test_goalkeeper_gets_gk_metrics_with_inverted_conceded() -> None:
    client = _client(
        [
            {
                "player_id": 1,
                "position_group": "GK",
                "goals_p90": 0.0,
                "conceded_p90": 1.1,
                "clean_sheet_rate": 0.4,
                "pct_conceded_p90": 0.25,
                "pct_clean_sheet_rate": 0.7,
            }
        ],
        player_row={"player_id": 1, "position_group": "GK", "sub_position": "Goalkeeper"},
    )
    body = client.get("/api/players/1/percentiles").json()

    by_metric = {m["metric"]: m for m in body["metrics"]}
    assert set(by_metric) == {"conceded_p90", "clean_sheet_rate"}
    # Conceding less than 75% of peers reads as the 75th percentile.
    assert by_metric["conceded_p90"]["percentile"] == 75
    assert by_metric["conceded_p90"]["direction"] == "lower_better"
    assert by_metric["clean_sheet_rate"]["percentile"] == 70
    assert by_metric["clean_sheet_rate"]["direction"] == "higher_better"


def test_latest_season_wins_then_minutes_break_same_season_ties() -> None:
    client = _client(
        [
            {"player_id": 1, "season": 2024, "league": "AA1", "minutes": 3000},
            {"player_id": 1, "season": 2025, "league": "AA1", "minutes": 500},
            {"player_id": 1, "season": 2025, "league": "BB1", "minutes": 1500},
        ]
    )
    body = client.get("/api/players/1/percentiles").json()
    assert body["season"] == 2025
    assert body["league_id"] == "BB1"
    assert body["minutes"] == 1500


def test_below_floor_row_keeps_peer_n_and_null_percentiles() -> None:
    client = _client(
        [
            {
                "player_id": 1,
                "minutes": 300,
                "pct_goals_p90": None,
                "pct_assists_p90": None,
                "pct_ga_p90": None,
                "pct_cards_p90": None,
                "peer_n": 55,
            }
        ]
    )
    body = client.get("/api/players/1/percentiles").json()

    assert body["below_floor"] is True
    assert all(m["percentile"] is None for m in body["metrics"])
    assert all(m["peer_n"] == 55 for m in body["metrics"])


def test_player_without_stats_has_no_metrics() -> None:
    client = _client([])
    body = client.get("/api/players/1/percentiles").json()
    assert body == {
        "player_id": 1,
        "has_stats": False,
        "season": None,
        "league_id": None,
        "minutes": None,
        "games_played": None,
        "below_floor": False,
        "metrics": [],
    }


def test_unknown_player_is_404() -> None:
    client = _client([])
    response = client.get("/api/players/999/percentiles")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "player_not_found"
