"""load_store round-trip on synthetic parquet + repository behavior."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from api_factories import (
    make_club_seasons,
    make_league_seasons,
    make_meta_payload,
    make_player_values,
    make_players_processed,
    make_profile_stats,
    make_transitions,
)

from app.repositories.store import load_store


def _write_processed(data_dir: Path) -> None:
    data_dir.mkdir(parents=True)
    make_players_processed([{"player_id": 1, "name": "Zlatan Ibrahimović"}]).write_parquet(
        data_dir / "players.parquet"
    )
    make_player_values(
        [
            {"player_id": 1, "date": date(2026, 1, 1), "market_value_eur": 5_000_000},
            {"player_id": 1, "date": date(2025, 1, 1), "market_value_eur": 4_000_000},
        ]
    ).write_parquet(data_dir / "player_values.parquet")
    make_transitions(
        [
            {"player_id": 100, "suspected_loan": False},
            {"player_id": 101, "transfer_date": date(2023, 8, 1), "suspected_loan": True},
        ]
    ).write_parquet(data_dir / "transitions.parquet")
    make_league_seasons(
        [{"league": "AA1", "season": 2024}, {"league": "AA1", "season": 2025}]
    ).write_parquet(data_dir / "league_seasons.parquet")
    make_club_seasons([{"club_id": 10, "season": 2025}]).write_parquet(
        data_dir / "club_seasons.parquet"
    )
    make_profile_stats([{"player_id": 1, "season": 2025}]).write_parquet(
        data_dir / "profile_stats.parquet"
    )
    (data_dir / "meta.json").write_text(json.dumps(make_meta_payload()))


def test_load_store_round_trip(tmp_path: Path) -> None:
    data_dir = tmp_path / "processed"
    _write_processed(data_dir)
    store = load_store(data_dir)

    player = store.players.get(1)
    assert player is not None
    assert player.name == "Zlatan Ibrahimović"

    history = store.players.value_history(1)
    assert [p.date for p in history] == [date(2025, 1, 1), date(2026, 1, 1)]  # sorted asc

    # The comps universe never contains suspected loans.
    assert store.transitions.comps_universe["player_id"].to_list() == [100]

    assert store.seasons.latest_season == 2025
    assert store.build_info.revision == "abc123"
    assert store.build_info.max_valuation_date == date(2026, 6, 12)
    assert store.build_info.comps_universe_size == 19_407


def test_load_store_missing_artifact_names_the_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "processed"
    _write_processed(data_dir)
    (data_dir / "transitions.parquet").unlink()
    with pytest.raises(FileNotFoundError, match=r"transitions\.parquet"):
        load_store(data_dir)


def test_players_get_unknown_id_returns_none(tmp_path: Path) -> None:
    data_dir = tmp_path / "processed"
    _write_processed(data_dir)
    store = load_store(data_dir)
    assert store.players.get(999) is None
