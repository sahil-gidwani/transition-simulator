"""End-to-end build on a ~30-row synthetic raw directory (never real data)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
from factories import (
    make_appearances,
    make_club_games,
    make_clubs,
    make_competitions,
    make_games,
    make_players,
    make_transfers,
    make_valuations,
)

from pipeline.build import run_build
from pipeline.config import HF_REPO, PINNED_HF_REVISION, Expectations, FunnelCounts

_BUILT_AT = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)


def _expectations(players_columns: int) -> Expectations:
    return Expectations(
        min_transfers=1,
        min_valuations=1,
        min_players=1,
        players_columns=players_columns,
        max_valuation_date=date(2021, 7, 1),
        censor_horizon=date(2021, 1, 2),
        funnel=FunnelCounts(
            raw=4, cleaned=3, in_scope=2, with_v_before=2, observable=2, with_v_after=2, non_loan=2
        ),
        min_transitions_non_loan=1,
        min_player_values=1,
        min_elo_touch_coverage=0.0,
        min_minutes_nonnull_legacy=0.0,
        max_total_bytes=50 * 1024 * 1024,
    )


def _write_raw(raw_dir: Path) -> int:
    """Build the synthetic raw dir; returns the players.csv column count."""
    raw_dir.mkdir(parents=True)
    (raw_dir / "external").mkdir()

    make_competitions([{"competition_id": "AA1"}, {"competition_id": "BB1"}]).write_csv(
        raw_dir / "competitions.csv"
    )

    def club(club_id: int, code: str, name: str, league: str) -> dict[str, object]:
        return {
            "club_id": club_id,
            "club_code": code,
            "name": name,
            "domestic_competition_id": league,
        }

    make_clubs(
        [
            club(10, "alpha", "Alpha FC", "AA1"),
            club(20, "beta", "Beta FC", "AA1"),
            club(30, "gamma", "Gamma FC", "BB1"),
            club(31, "delta", "Delta FC", "BB1"),
        ]
    ).write_csv(raw_dir / "clubs.csv")
    players = make_players(
        [
            {"player_id": 1, "name": "Striker One", "current_club_id": 20},
            {
                "player_id": 2,
                "name": "Keeper Two",
                "sub_position": "Goalkeeper",
                "position": "Goalkeeper",
                "current_club_id": 30,
                "current_club_domestic_competition_id": "BB1",
            },
        ]
    ).with_columns(international_caps=pl.lit(0))
    players.write_csv(raw_dir / "players.csv")
    make_valuations(
        [
            {"player_id": 1, "date": date(2019, 8, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 1, "date": date(2020, 5, 1), "market_value_in_eur": 2_000_000},
            {
                "player_id": 1,
                "date": date(2021, 7, 1),
                "market_value_in_eur": 5_000_000,
                "current_club_id": 20,
            },
            {
                "player_id": 2,
                "date": date(2020, 5, 1),
                "market_value_in_eur": 500_000,
                "current_club_id": 20,
            },
            {
                "player_id": 2,
                "date": date(2021, 6, 1),
                "market_value_in_eur": 600_000,
                "current_club_id": 30,
            },
        ]
    ).write_csv(raw_dir / "player_valuations.csv")
    make_transfers(
        [
            {
                "player_id": 1,
                "transfer_date": date(2020, 7, 1),
                "from_club_id": 10,
                "to_club_id": 20,
            },
            {
                "player_id": 2,
                "transfer_date": date(2020, 7, 5),
                "from_club_id": 20,
                "to_club_id": 30,
                "transfer_fee": 0.0,
            },
            {
                "player_id": 1,
                "transfer_date": date(2015, 7, 1),
                "from_club_id": 99,
                "to_club_id": 10,
            },
            {"player_id": 2, "transfer_date": None},
        ]
    ).write_csv(raw_dir / "transfers.csv")
    make_games(
        [
            {"game_id": 100, "date": date(2020, 8, 1), "home_club_id": 10, "away_club_id": 20},
            {"game_id": 101, "date": date(2020, 8, 8), "home_club_id": 20, "away_club_id": 10},
            {
                "game_id": 200,
                "date": date(2020, 9, 1),
                "home_club_id": 30,
                "away_club_id": 31,
                "competition_id": "BB1",
            },
        ]
    ).write_csv(raw_dir / "games.csv")
    make_appearances(
        [
            {
                "game_id": 100,
                "player_id": 1,
                "player_club_id": 20,
                "goals": 1,
                "date": date(2020, 8, 1),
            },
            {"game_id": 101, "player_id": 1, "player_club_id": 20, "date": date(2020, 8, 8)},
            {
                "game_id": 200,
                "player_id": 2,
                "player_club_id": 30,
                "competition_id": "BB1",
                "date": date(2020, 9, 1),
            },
        ]
    ).write_csv(raw_dir / "appearances.csv")
    make_club_games(
        [
            {"game_id": 100, "club_id": 20, "opponent_id": 10, "opponent_goals": 0},
            {"game_id": 101, "club_id": 20, "opponent_id": 10, "opponent_goals": 1},
            {"game_id": 200, "club_id": 30, "opponent_id": 31, "opponent_goals": 0},
        ]
    ).write_csv(raw_dir / "club_games.csv")

    (raw_dir / "external" / "eloratings_bimonthly.csv").write_text(
        '"date","club","country","elo"\n'
        '"2020-06-15","Alpha","ALA","1500.0"\n'
        '"2020-06-15","Beta","ALA","1600.0"\n'
    )
    (raw_dir / "external" / "clubelo_daily.csv").write_text(
        "Rank,Club,Country,Level,Elo,From,To,date,updated_at\n"
        "1.0,Gamma,ALA,1,1400.0,2020-06-01,2020-06-15,2020-06-15,2020-06-15 10:00:00\n"
    )
    (raw_dir / "external" / "team_mapping.csv").write_text(
        "country,id_opta,team_opta,n_opta,team_clubelo\n"
    )
    (raw_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "tables_source": {
                    "source": "huggingface",
                    "repo": HF_REPO,
                    "revision": PINNED_HF_REVISION,
                },
                "files": {},
            }
        )
    )
    return players.width


def _write_manual(path: Path, elo_name: str = "Alpha") -> None:
    path.write_text(f"elo_name,club_id,tm_name,note\n{elo_name},10,Alpha FC,test row\n")


def _run(tmp_path: Path, expectations: Expectations | None = None) -> tuple[int, Path, Path]:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "processed"
    report = tmp_path / "report.md"
    manual = tmp_path / "manual.csv"
    if not raw_dir.exists():
        cols = _write_raw(raw_dir)
        _write_manual(manual)
    else:
        cols = pl.read_csv(raw_dir / "players.csv").width
    code = run_build(
        raw_dir=raw_dir,
        out_dir=out_dir,
        report_path=report,
        manual_fixes_path=manual,
        expectations=expectations or _expectations(cols),
        built_at=_BUILT_AT,
    )
    return code, out_dir, report


def test_build_succeeds_and_writes_all_artifacts(tmp_path: Path) -> None:
    code, out_dir, report = _run(tmp_path)
    assert code == 0
    names = sorted(p.name for p in out_dir.iterdir())
    assert names == [
        "club_seasons.parquet",
        "elo_mapping.parquet",
        "league_seasons.parquet",
        "meta.json",
        "player_values.parquet",
        "players.parquet",
        "profile_stats.parquet",
        "transitions.parquet",
    ]
    assert report.exists()

    meta = json.loads((out_dir / "meta.json").read_text())
    assert meta["funnel"]["raw"] == 4
    assert meta["funnel"]["non_loan"] == 2
    assert meta["valuation_freshness"]["max_valuation_date"] == "2021-07-01"

    transitions = pl.read_parquet(out_dir / "transitions.parquet")
    assert transitions.height == 2
    striker = transitions.filter(pl.col("player_id") == 1).row(0, named=True)
    assert striker["multiplier"] == 2.5
    assert striker["from_league"] == "AA1"
    assert striker["from_elo"] == 1500.0  # manual fix maps Alpha FC -> Alpha
    assert striker["to_elo"] == 1600.0
    assert not striker["suspected_loan"]

    profile = pl.read_parquet(out_dir / "profile_stats.parquet")
    keeper = profile.filter(pl.col("player_id") == 2).row(0, named=True)
    assert keeper["clean_sheet_rate"] == 1.0

    values = pl.read_parquet(out_dir / "player_values.parquet")
    assert values.height == 5  # both synthetic players are in scope, all rows dated
    assert values["player_id"].to_list() == sorted(values["player_id"].to_list())

    mapping = pl.read_parquet(out_dir / "elo_mapping.parquet")
    assert mapping.filter(pl.col("club_id") == 10)["stage"].to_list() == ["manual"]


def test_rebuild_is_byte_identical(tmp_path: Path) -> None:
    code1, out_dir, _ = _run(tmp_path)
    assert code1 == 0
    first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out_dir.iterdir())}
    code2, out_dir, _ = _run(tmp_path)
    assert code2 == 0
    second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out_dir.iterdir())}
    assert first == second


def test_wrong_revision_fails_before_any_output(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    cols = _write_raw(raw_dir)
    _write_manual(tmp_path / "manual.csv")
    manifest = json.loads((raw_dir / "MANIFEST.json").read_text())
    manifest["tables_source"]["revision"] = "deadbeef"
    (raw_dir / "MANIFEST.json").write_text(json.dumps(manifest))
    code, out_dir, report = _run(tmp_path, _expectations(cols))
    assert code == 1
    assert not out_dir.exists()
    assert not report.exists()


def test_frozen_valuations_fail_the_freshness_gate(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    cols = _write_raw(raw_dir)
    _write_manual(tmp_path / "manual.csv")
    vals = pl.read_csv(raw_dir / "player_valuations.csv", try_parse_dates=True)
    vals.filter(pl.col("date") < date(2021, 7, 1)).write_csv(raw_dir / "player_valuations.csv")
    code, out_dir, _ = _run(tmp_path, _expectations(cols))
    assert code == 1
    assert not out_dir.exists()


def test_funnel_drift_fails_and_leaves_no_artifacts(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    cols = _write_raw(raw_dir)
    _write_manual(tmp_path / "manual.csv")
    exp = _expectations(cols)
    drifted = replace(exp, funnel=replace(exp.funnel, non_loan=3))
    code, out_dir, report = _run(tmp_path, drifted)
    assert code == 1
    assert not list(out_dir.glob("*.parquet"))
    assert not (out_dir / "meta.json").exists()
    assert not report.exists()


def test_unresolvable_manual_fix_fails(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    cols = _write_raw(raw_dir)
    _write_manual(tmp_path / "manual.csv", elo_name="Alhpa")  # typo: not in the mirrors
    code, out_dir, _ = _run(tmp_path, _expectations(cols))
    assert code == 1
    assert not out_dir.exists()
