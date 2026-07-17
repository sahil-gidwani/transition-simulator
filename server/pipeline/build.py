"""Build orchestrator: raw datasets -> hard gates -> committed parquet artifacts.

Run from server/ with the data group installed:

    uv run python -m pipeline.build

Artifacts are written to a temp directory and promoted only after every gate
passes; a failing build exits non-zero, prints the full gate table and leaves
data/processed/ untouched.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from pipeline import io
from pipeline.config import (
    HF_REPO,
    LEGACY_LEAGUES,
    MANUAL_ELO_FIXES_CSV,
    PINNED_EXPECTATIONS,
    PINNED_HF_REVISION,
    PROCESSED_DIR_DEFAULT,
    RAW_DIR_DEFAULT,
    REPORT_MD_DEFAULT,
    SEASON_MIN,
    SEASON_START_MONTH,
    Expectations,
)
from pipeline.gates import (
    GateResult,
    all_passed,
    check_elo_coverage,
    check_funnel,
    check_key_uniqueness,
    check_manifest_pin,
    check_manual_fixes,
    check_minutes_coverage,
    check_non_empty,
    check_players_schema,
    check_table_floors,
    check_total_size,
    check_transitions_floor,
    check_valuation_freshness,
    render_gate_table,
)
from pipeline.report import BuildMeta, meta_json, report_md
from pipeline.transforms import elo as elo_t
from pipeline.transforms import leagues as leagues_t
from pipeline.transforms import minutes as minutes_t
from pipeline.transforms import profile as profile_t
from pipeline.transforms.common import (
    club_league_by_season,
    covered_clubs,
    covered_league_ids,
)
from pipeline.transforms.loans import flag_suspected_loans
from pipeline.transforms.players import assemble_players
from pipeline.transforms.squads import assemble_club_seasons, squad_values
from pipeline.transforms.transfers import annotate_scope, clean_transfers
from pipeline.transforms.transitions import (
    assemble_transitions,
    attach_player_attrs,
    elo_keys,
    filter_universe_rows,
    minutes_anchors,
)
from pipeline.transforms.windows import (
    attach_outcomes,
    attach_v_after,
    attach_v_before,
    compute_funnel,
    max_valuation_date,
)

CLUB_SEASONS_SCHEMA: dict[str, pl.DataType] = {
    "club_id": pl.Int32(),
    "season": pl.Int16(),
    "club_name": pl.String(),
    "league": pl.String(),
    "league_source": pl.String(),
    "squad_value_eur": pl.Int64(),
    "n_valued_players": pl.Int16(),
    "tercile": pl.Int8(),
    "elo": pl.Float32(),
    "elo_pct": pl.Float32(),
    "elo_date": pl.Date(),
    "elo_mapped": pl.Boolean(),
}

LEAGUE_SEASONS_SCHEMA: dict[str, pl.DataType] = {
    "league": pl.String(),
    "season": pl.Int16(),
    "n_clubs": pl.Int16(),
    "median_squad_value_eur": pl.Int64(),
    "strength": pl.Float64(),
    "tier": pl.Int8(),
    "median_elo": pl.Float32(),
    "elo_club_coverage": pl.Float32(),
}

ELO_MAPPING_SCHEMA: dict[str, pl.DataType] = {
    "club_id": pl.Int32(),
    "tm_name": pl.String(),
    "league": pl.String(),
    "elo_name": pl.String(),
    "stage": pl.String(),
    "mapped": pl.Boolean(),
    "in_universe": pl.Boolean(),
    "universe_touches": pl.Int32(),
}

PROFILE_SCHEMA: dict[str, pl.DataType] = {
    "player_id": pl.Int32(),
    "season": pl.Int16(),
    "league": pl.String(),
    "position_group": pl.String(),
    "games_played": pl.Int16(),
    "minutes": pl.Int32(),
    "goals": pl.Int16(),
    "assists": pl.Int16(),
    "cards": pl.Int16(),
    "minutes_share": pl.Float32(),
    "goals_p90": pl.Float32(),
    "assists_p90": pl.Float32(),
    "ga_p90": pl.Float32(),
    "cards_p90": pl.Float32(),
    "conceded_p90": pl.Float32(),
    "clean_sheet_rate": pl.Float32(),
    "pct_goals_p90": pl.Float32(),
    "pct_assists_p90": pl.Float32(),
    "pct_ga_p90": pl.Float32(),
    "pct_cards_p90": pl.Float32(),
    "pct_conceded_p90": pl.Float32(),
    "pct_clean_sheet_rate": pl.Float32(),
    "peer_n": pl.Int16(),
}


def _cast(df: pl.DataFrame, schema: dict[str, pl.DataType], sort: list[str]) -> pl.DataFrame:
    return df.select(*(pl.col(name).cast(dtype) for name, dtype in schema.items())).sort(sort)


def _season_of_date(d: date) -> int:
    return d.year - (1 if d.month < SEASON_START_MONTH else 0)


def _log(message: str) -> None:
    print(f"==> {message}", flush=True)


def run_build(
    raw_dir: Path,
    out_dir: Path,
    report_path: Path,
    manual_fixes_path: Path,
    expectations: Expectations,
    built_at: datetime,
    keep_tmp: bool = False,
) -> int:
    # --- phase 1: input gates -------------------------------------------------
    pin_gate = check_manifest_pin(io.read_manifest(raw_dir), HF_REPO, PINNED_HF_REVISION)
    if not pin_gate.passed:
        print(render_gate_table([pin_gate]), file=sys.stderr)
        return 1

    _log("loading raw tables")
    raw = io.load_raw(raw_dir)
    transfers_df = raw.transfers.collect()
    valuations_df = raw.valuations.collect()
    players_df = raw.players.collect()
    clubs_df = raw.clubs.collect()
    competitions_df = raw.competitions.collect()

    manual = io.load_manual_fixes(manual_fixes_path)
    bimonthly, daily = io.load_elo_mirrors(raw_dir)
    unified = elo_t.unify_mirrors(bimonthly, daily)
    elo_names: list[str] = unified["elo_name"].unique().sort().to_list()
    max_val = max_valuation_date(valuations_df)

    input_gates: list[GateResult] = [pin_gate]
    input_gates += check_table_floors(
        transfers_df.height, valuations_df.height, players_df.height, expectations
    )
    input_gates.append(check_players_schema(players_df.columns, expectations))
    input_gates.append(check_valuation_freshness(max_val, expectations))
    input_gates.append(
        check_manual_fixes(manual, set(elo_names), set(clubs_df["club_id"].to_list()))
    )
    if not all_passed(input_gates):
        print(render_gate_table(input_gates), file=sys.stderr)
        return 1

    games_df = raw.games.select(
        "game_id",
        "competition_id",
        "season",
        "date",
        "home_club_id",
        "away_club_id",
        "competition_type",
    ).collect()
    appearances_df = raw.appearances.select(
        "game_id",
        "player_id",
        "player_club_id",
        "date",
        "competition_id",
        "yellow_cards",
        "red_cards",
        "goals",
        "assists",
        "minutes_played",
    ).collect()
    club_games_df = raw.club_games.select("game_id", "club_id", "opponent_goals").collect()

    # --- funnel base ------------------------------------------------------------
    _log("funnel: cleaning, loans, valuation windows")
    covered = covered_clubs(clubs_df, competitions_df)
    cleaned, cleaning = clean_transfers(transfers_df)
    tf = annotate_scope(cleaned, covered["club_id"].to_list())
    tf, _loan_counts = flag_suspected_loans(tf)
    tf = attach_v_before(tf, valuations_df)
    tf = attach_v_after(tf, valuations_df)
    tf = attach_outcomes(tf, max_val)
    funnel = compute_funnel(tf, cleaning)

    # --- club & league strength ---------------------------------------------------
    _log("club seasons: derived squad values, leagues, terciles")
    seasons = list(range(SEASON_MIN, _season_of_date(max_val) + 1))
    squads = squad_values(valuations_df, seasons)
    games_leagues = club_league_by_season(games_df)
    club_seasons_work = assemble_club_seasons(squads, games_leagues, clubs_df, competitions_df)

    _log("clubelo: mapping ladder and season-start ratings")
    covered_full = clubs_df.select(
        "club_id", "name", "club_code", "domestic_competition_id"
    ).filter(pl.col("club_id").is_in(covered["club_id"].to_list()))
    reep_bridge = io.load_reep_team_bridge(raw_dir)
    team_mapping = io.load_team_mapping(raw_dir)
    mapping = elo_t.build_elo_mapping(covered_full, elo_names, reep_bridge, team_mapping, manual)
    auto_mapping = elo_t.build_elo_mapping(
        covered_full, elo_names, reep_bridge, team_mapping, manual.clear()
    )
    warnings = [
        f"manual Elo fix for club {cid} ({name}) is now found automatically - consider removing"
        for cid, name in manual.select("club_id", "tm_name").iter_rows()
        if auto_mapping.filter(pl.col("club_id") == cid)["elo_name"].to_list()
        == mapping.filter(pl.col("club_id") == cid)["elo_name"].to_list()
    ]

    cs_keys = club_seasons_work.with_columns(
        asof_date=pl.date(pl.col("season"), SEASON_START_MONTH, 1)
    )
    club_seasons_enriched = elo_t.elo_asof(cs_keys, unified, mapping).drop("asof_date")
    club_seasons_final = _cast(
        club_seasons_enriched, CLUB_SEASONS_SCHEMA, ["season", "league", "club_id"]
    )

    league_seasons_work = leagues_t.league_seasons(club_seasons_enriched)
    league_seasons_final = _cast(league_seasons_work, LEAGUE_SEASONS_SCHEMA, ["season", "league"])

    # --- transitions ------------------------------------------------------------
    _log("transitions: universe, minutes share, transfer-date elo")
    rows_all = attach_player_attrs(tf, players_df)
    urows = filter_universe_rows(rows_all)
    league_ids = covered_league_ids(competitions_df)
    covered_games = minutes_t.covered_league_games(games_df, appearances_df)
    mshare = minutes_t.minutes_share(
        minutes_anchors(urows), cleaned, covered_games, appearances_df, league_ids
    )
    e_from = elo_t.elo_asof(elo_keys(urows, "from"), unified, mapping)
    e_to = elo_t.elo_asof(elo_keys(urows, "to"), unified, mapping)
    season32 = pl.col("season").cast(pl.Int32)
    transitions_df = assemble_transitions(
        urows,
        club_seasons_work.with_columns(season32),
        league_seasons_work.with_columns(season32),
        mshare,
        e_from,
        e_to,
    )

    audit_universe = tf.filter(
        pl.col("in_scope")
        & pl.col("v_before").is_not_null()
        & pl.col("v_after").is_not_null()
        & ~pl.col("censored")
        & ~pl.col("suspected_loan")
    )
    touches = (
        pl.concat(
            [
                audit_universe.select(club_id=pl.col("from_club_id")),
                audit_universe.select(club_id=pl.col("to_club_id")),
            ]
        )
        .group_by("club_id")
        .agg(universe_touches=pl.len())
    )
    mapping_final = _cast(
        elo_t.attach_universe_flags(mapping, touches), ELO_MAPPING_SCHEMA, ["club_id"]
    )

    # --- players & profile ------------------------------------------------------
    _log("players and profile stats")
    players_final = assemble_players(players_df, valuations_df, competitions_df)
    stats = profile_t.player_season_stats(appearances_df, games_df)
    gk = profile_t.gk_stats(appearances_df, games_df, club_games_df)
    pshare = profile_t.profile_minutes_share(appearances_df, games_df, cleaned, covered_games)
    profile_final = _cast(
        profile_t.assemble_profile_stats(stats, gk, players_df, pshare),
        PROFILE_SCHEMA,
        ["player_id", "season", "league"],
    )

    # --- write to temp, gate, promote --------------------------------------------
    tmp_dir = out_dir / ".tmp-build"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    artifacts = [
        io.write_artifact(players_final, tmp_dir, "players.parquet"),
        io.write_artifact(club_seasons_final, tmp_dir, "club_seasons.parquet"),
        io.write_artifact(league_seasons_final, tmp_dir, "league_seasons.parquet"),
        io.write_artifact(transitions_df, tmp_dir, "transitions.parquet"),
        io.write_artifact(profile_final, tmp_dir, "profile_stats.parquet"),
        io.write_artifact(mapping_final, tmp_dir, "elo_mapping.parquet"),
    ]

    universe_mapping = mapping_final.filter(pl.col("in_universe"))
    touch_total = int(universe_mapping["universe_touches"].sum() or 0)
    touch_mapped = int(universe_mapping.filter(pl.col("mapped"))["universe_touches"].sum() or 0)
    elo_coverage = touch_mapped / touch_total if touch_total else 0.0
    legacy = transitions_df.filter(
        pl.col("from_league").is_in(list(LEGACY_LEAGUES)) & (pl.col("season") >= SEASON_MIN + 1)
    )
    minutes_coverage = (
        int(legacy["minutes_share_pre"].is_not_null().sum() or 0) / legacy.height
        if legacy.height
        else 0.0
    )
    non_loan_count = transitions_df.filter(~pl.col("suspected_loan")).height

    gates = list(input_gates)
    gates += check_funnel(funnel, expectations.funnel)
    gates.append(check_transitions_floor(non_loan_count, expectations))
    gates.append(check_elo_coverage(elo_coverage, expectations))
    gates.append(check_minutes_coverage(minutes_coverage, expectations))
    gates.append(check_key_uniqueness(players_final, ["player_id"], "players"))
    gates.append(check_key_uniqueness(club_seasons_final, ["club_id", "season"], "club_seasons"))
    gates.append(check_key_uniqueness(league_seasons_final, ["league", "season"], "league_seasons"))
    gates.append(
        check_key_uniqueness(transitions_df, ["player_id", "transfer_date"], "transitions")
    )
    gates.append(
        check_key_uniqueness(profile_final, ["player_id", "season", "league"], "profile_stats")
    )
    gates.append(check_key_uniqueness(mapping_final, ["club_id"], "elo_mapping"))
    gates += [
        check_non_empty(df, name)
        for df, name in [
            (players_final, "players"),
            (club_seasons_final, "club_seasons"),
            (league_seasons_final, "league_seasons"),
            (transitions_df, "transitions"),
            (profile_final, "profile_stats"),
            (mapping_final, "elo_mapping"),
        ]
    ]
    gates.append(check_total_size(sum(a.n_bytes for a in artifacts), expectations))

    stage_weights = {
        str(stage): int(weight)
        for stage, weight in universe_mapping.group_by("stage")
        .agg(pl.col("universe_touches").sum())
        .sort("stage")
        .iter_rows()
    }
    league_sources = {
        f"club_seasons_league_source_{source}": int(n)
        for source, n in club_seasons_final.group_by("league_source")
        .agg(pl.len())
        .sort("league_source")
        .iter_rows()
    }
    latest_season_raw = league_seasons_final["season"].max()
    latest_season = int(latest_season_raw) if isinstance(latest_season_raw, int) else 0
    tier_boundaries = [
        f"- Tier {tier}: {n} leagues, median club squad value €{lo:,.0f} - €{hi:,.0f}"
        for tier, n, lo, hi in league_seasons_final.filter(pl.col("season") == latest_season)
        .group_by("tier")
        .agg(
            n=pl.len(),
            lo=pl.col("median_squad_value_eur").min(),
            hi=pl.col("median_squad_value_eur").max(),
        )
        .sort("tier")
        .iter_rows()
    ]

    meta = BuildMeta(
        repo=HF_REPO,
        revision=PINNED_HF_REVISION,
        built_at=built_at.isoformat(timespec="seconds"),
        polars_version=pl.__version__,
        max_valuation_date=max_val.isoformat(),
        censor_horizon=(expectations.censor_horizon).isoformat(),
        funnel=funnel,
        transitions_rows=transitions_df.height,
        transitions_non_loan=non_loan_count,
        gates=gates,
        coverage={
            "elo_touch_coverage": round(elo_coverage, 4),
            "minutes_share_nonnull_legacy_2013_plus": round(minutes_coverage, 4),
            **{f"elo_stage_touches_{k}": v for k, v in stage_weights.items()},
            **league_sources,
        },
        constants={
            "v_before_window_days": [1, 180],
            "v_after_window_days": [180, 540],
            "loan_max_return_days": 548,
            "season_min": SEASON_MIN,
            "elo_asof_tolerance_days": 45,
            "squad_value_staleness_days": 365,
            "minutes_window_days": 365,
            "profile_min_minutes": 450,
        },
        artifacts=artifacts,
        warnings=warnings,
        tier_boundaries=tier_boundaries,
    )

    if not all_passed(gates):
        print(render_gate_table(gates), file=sys.stderr)
        if not keep_tmp:
            shutil.rmtree(tmp_dir)
        return 1

    io.write_json(meta_json(meta), tmp_dir, "meta.json")
    io.promote(tmp_dir, out_dir)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md(meta), encoding="utf-8", newline="\n")
    print(render_gate_table(gates))
    total_mb = sum(a.n_bytes for a in artifacts) / 1024 / 1024
    _log(f"promoted {len(artifacts)} artifacts + meta.json ({total_mb:.1f} MB) to {out_dir}")
    _log(f"report written to {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR_DEFAULT)
    parser.add_argument("--out-dir", type=Path, default=PROCESSED_DIR_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_MD_DEFAULT)
    parser.add_argument("--keep-tmp", action="store_true", help="keep .tmp-build on failure")
    args = parser.parse_args(argv)
    return run_build(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        report_path=args.report_path,
        manual_fixes_path=MANUAL_ELO_FIXES_CSV,
        expectations=PINNED_EXPECTATIONS,
        built_at=datetime.now(UTC),
        keep_tmp=args.keep_tmp,
    )


if __name__ == "__main__":
    sys.exit(main())
