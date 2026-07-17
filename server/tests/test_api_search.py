"""GET /api/players/search contract: normalization, ranking, limits."""

from __future__ import annotations

from api_factories import make_client, make_league_seasons, make_players_processed, make_store


def _client_with_players(rows: list[dict[str, object]]) -> object:
    store = make_store(
        players=make_players_processed(list(rows)),
        league_seasons=make_league_seasons([{"league": "AA1", "league_name": "premier-league"}]),
    )
    return make_client(store)


def test_search_is_diacritic_and_case_insensitive() -> None:
    client = _client_with_players(
        [
            {"player_id": 1, "name": "Mesut Özil"},
            {"player_id": 2, "name": "Alexander Sørloth"},
            {"player_id": 3, "name": "John Smith"},
        ]
    )
    assert [r["name"] for r in client.get("/api/players/search", params={"q": "OZIL"}).json()] == [
        "Mesut Özil"
    ]
    assert [
        r["name"] for r in client.get("/api/players/search", params={"q": "sørloth"}).json()
    ] == ["Alexander Sørloth"]


def test_search_ranks_prefix_over_token_prefix_over_substring() -> None:
    client = _client_with_players(
        [
            {"player_id": 1, "name": "Amartinez Zed", "market_value_eur": 1_000_000},
            {"player_id": 2, "name": "Lisandro Martinez", "market_value_eur": 1_000_000},
            {"player_id": 3, "name": "Martinez Lautaro", "market_value_eur": 1_000_000},
        ]
    )
    names = [r["name"] for r in client.get("/api/players/search", params={"q": "martinez"}).json()]
    assert names == ["Martinez Lautaro", "Lisandro Martinez", "Amartinez Zed"]


def test_search_ties_break_by_market_value_desc_nulls_last() -> None:
    client = _client_with_players(
        [
            {"player_id": 1, "name": "Silva One", "market_value_eur": 1_000_000},
            {"player_id": 2, "name": "Silva Two", "market_value_eur": 50_000_000},
            {
                "player_id": 3,
                "name": "Silva Three",
                "market_value_eur": None,
                "market_value_asof": None,
            },
        ]
    )
    names = [r["name"] for r in client.get("/api/players/search", params={"q": "silva"}).json()]
    assert names == ["Silva Two", "Silva One", "Silva Three"]


def test_search_query_below_two_normalized_chars_returns_empty() -> None:
    client = _client_with_players([{"player_id": 1, "name": "Xavi"}])
    assert client.get("/api/players/search", params={"q": "x"}).json() == []
    assert client.get("/api/players/search", params={"q": " ç "}).json() == []


def test_multi_token_query_spans_the_name_boundary() -> None:
    # The dominant real query shape: first name + partial last name.
    client = _client_with_players(
        [
            {"player_id": 1, "name": "Mesut Özil"},
            {"player_id": 2, "name": "Mesut Another"},
        ]
    )
    results = client.get("/api/players/search", params={"q": "mesut oz"}).json()
    assert [r["name"] for r in results] == ["Mesut Özil"]
    # Substrings crossing a token boundary still match (rank: contains).
    inner = client.get("/api/players/search", params={"q": "sut ozi"}).json()
    assert [r["name"] for r in inner] == ["Mesut Özil"]


def test_search_caps_results_at_twenty() -> None:
    rows = [{"player_id": i, "name": f"Clone Player {i:02d}"} for i in range(1, 26)]
    client = _client_with_players(rows)
    assert len(client.get("/api/players/search", params={"q": "clone"}).json()) == 20


def test_search_result_shape_includes_value_asof_and_league_label() -> None:
    client = _client_with_players([{"player_id": 7, "name": "Shape Check"}])
    (row,) = client.get("/api/players/search", params={"q": "shape"}).json()
    assert row == {
        "player_id": 7,
        "name": "Shape Check",
        "age": 28,  # born 1998-06-15, FixedClock 2026-07-17
        "position_group": "ATT",
        "sub_position": "Centre-Forward",
        "club_name": "Alpha FC",
        "league_id": "AA1",
        "league_name": "Premier League",
        "market_value_eur": 10_000_000,
        "market_value_asof": "2026-06-01",
    }


def test_search_missing_query_param_uses_error_schema() -> None:
    client = _client_with_players([])
    response = client.get("/api/players/search")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["detail"]
