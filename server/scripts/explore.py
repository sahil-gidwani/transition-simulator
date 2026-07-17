"""Audit the raw datasets behind Precedent.

Reads server/data/raw/ (see scripts/download_data.py), computes the
acceptance gates and feasibility analyses that docs/data-notes.md reports,
and writes server/data/raw/audit/audit_report.{md,json}. Deterministic:
re-running on the same raw files produces identical artifacts.

Exit code is non-zero when any acceptance gate fails; all sections still run.

Usage (from server/):
    uv run --group data python scripts/explore.py
    uv run --group data python scripts/explore.py --sections gates,funnel
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import polars as pl

RAW_DIR_DEFAULT = Path(__file__).resolve().parents[1] / "data" / "raw"

# --- audit constants -------------------------------------------------------

GATE_MIN_TRANSFERS = 150_000
GATE_MIN_VALUATIONS = 500_000
GATE_MIN_PLAYERS = 30_000
GATE_PLAYERS_COLUMNS = 26

V_BEFORE_MAX_DAYS = 180  # v_before: last valuation strictly before transfer, within 180d
V_AFTER_MIN_DAYS = 180  # v_after: first valuation in [t+180d, t+540d]
V_AFTER_MAX_DAYS = 540
LOAN_MAX_RETURN_DAYS = 548  # ~18 months: A->B then B->A within this gap smells like a loan

POSITION_GROUPS: dict[str, str] = {
    "Goalkeeper": "GK",
    "Centre-Back": "DEF",
    "Left-Back": "DEF",
    "Right-Back": "DEF",
    "Defensive Midfield": "MID",
    "Central Midfield": "MID",
    "Attacking Midfield": "MID",
    "Left Midfield": "MID",
    "Right Midfield": "MID",
    "Left Winger": "ATT",
    "Right Winger": "ATT",
    "Second Striker": "ATT",
    "Centre-Forward": "ATT",
}
COARSE_POSITION_GROUPS: dict[str, str] = {
    "Goalkeeper": "GK",
    "Defender": "DEF",
    "Midfield": "MID",
    "Attack": "ATT",
}

NEW_LEAGUES: tuple[str, ...] = ("MLS1", "BRA1", "ARG1", "JAP1", "RSK1", "MEX1", "AUS1", "SA1")

PSEUDO_CLUB_PATTERN = r"(?i)retired|without club|unknown|career break|ban"

# Corporate/legal tokens dropped when normalizing club names for Elo matching.
# NB: no token that is itself a distinguishing club name ("sporting", "sg" in
# "Paris SG") - dropping those creates collisions between distinct clubs.
_STOP_TOKENS = frozenset(
    {
        # abbreviations of club/association legal forms
        "fc",
        "cf",
        "afc",
        "ac",
        "as",
        "sc",
        "ssc",
        "sv",
        "bsc",
        "vfb",
        "vfl",
        "tsg",
        "fk",
        "nk",
        "if",
        "bk",
        "sk",
        "cd",
        "ud",
        "rcd",
        "ogc",
        "aj",
        "rc",
        "us",
        "sd",
        "ca",
        "kaa",
        "krc",
        "rsc",
        "kv",
        "sl",
        "gd",
        "cs",
        "fsv",
        "spvgg",
        "tsv",
        "cfr",
        "acf",
        "cp",
        "ab",
        "bsk",
        "fak",
        "spvg",
        "ag",
        "ev",
        "sad",
        "pfk",
        # spelled-out legal/generic words
        "club",
        "clube",
        "de",
        "futbol",
        "futebol",
        "calcio",
        "football",
        "fussball",
        "koninklijke",
        "voetbalvereniging",
        "vereniging",
        "sportvereniging",
        "sportverein",
        "spielvereinigung",
        "idraetsforening",
        "boldklub",
        "fodbold",
        "balompie",
        "sport",
        "esporte",
        "esportiva",
        "sociedade",
        "regatas",
    }
)

# Characters NFKD/ASCII would mangle; both sides of every match pass through this.
_TRANSLIT = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "ø": "oe",
        "æ": "ae",
        "å": "aa",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "þ": "th",
        "œ": "oe",
        "ı": "i",  # noqa: RUF001 - Turkish dotless i, intentional
    }
)


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


@dataclass
class SectionResult:
    name: str
    lines: list[str]
    metrics: dict[str, object]
    gates: list[Gate] = field(default_factory=list)


@dataclass(frozen=True)
class Tables:
    players: pl.LazyFrame
    valuations: pl.LazyFrame
    transfers: pl.LazyFrame
    appearances: pl.LazyFrame
    clubs: pl.LazyFrame
    competitions: pl.LazyFrame
    games: pl.LazyFrame


@dataclass
class AuditContext:
    raw_dir: Path
    tables: Tables
    _funnel: pl.DataFrame | None = None
    _funnel_meta: dict[str, object] | None = None
    _tiers: pl.DataFrame | None = None

    @property
    def external_dir(self) -> Path:
        return self.raw_dir / "external"

    def funnel(self) -> tuple[pl.DataFrame, dict[str, object]]:
        if self._funnel is None or self._funnel_meta is None:
            self._funnel, self._funnel_meta = build_funnel_base(self.tables)
        return self._funnel, self._funnel_meta

    def league_tiers(self) -> pl.DataFrame:
        if self._tiers is None:
            self._tiers = derive_preview_league_tiers(self.tables)
        return self._tiers


# --- loading ---------------------------------------------------------------


def _ensure_date(lf: pl.LazyFrame, columns: Iterable[str]) -> pl.LazyFrame:
    schema = lf.collect_schema()
    exprs: list[pl.Expr] = []
    for col in columns:
        dtype = schema.get(col)
        if dtype == pl.String:
            exprs.append(pl.col(col).str.to_date(strict=False))
        elif isinstance(dtype, pl.Datetime):
            exprs.append(pl.col(col).cast(pl.Date))
    return lf.with_columns(exprs) if exprs else lf


def load_tables(raw_dir: Path) -> Tables:
    def scan(name: str) -> pl.LazyFrame:
        return pl.scan_csv(raw_dir / name, try_parse_dates=True, infer_schema_length=10_000)

    return Tables(
        players=_ensure_date(scan("players.csv"), ["date_of_birth"]),
        valuations=_ensure_date(scan("player_valuations.csv"), ["date"]),
        transfers=_ensure_date(scan("transfers.csv"), ["transfer_date"]),
        appearances=_ensure_date(scan("appearances.csv"), ["date"]),
        clubs=scan("clubs.csv"),
        competitions=scan("competitions.csv"),
        games=_ensure_date(scan("games.csv"), ["date"]),
    )


# --- shared derivations ----------------------------------------------------


def season_of(col: str) -> pl.Expr:
    """Season label as its starting year, July-June (Jan window belongs to prior label)."""
    d = pl.col(col)
    return (d.dt.year() - (d.dt.month() < 7).cast(pl.Int32)).alias("season")


def covered_club_ids(t: Tables) -> tuple[set[int], pl.DataFrame]:
    """Club ids whose (snapshot) domestic competition is a covered domestic league."""
    comps = t.competitions.select("competition_id", "type", "name", "country_name").collect()
    domestic = set(comps.filter(pl.col("type") == "domestic_league")["competition_id"].to_list())
    clubs = t.clubs.select("club_id", "name", "domestic_competition_id").collect()
    covered = clubs.filter(pl.col("domestic_competition_id").is_in(sorted(domestic)))
    return set(covered["club_id"].to_list()), covered


def build_funnel_base(t: Tables) -> tuple[pl.DataFrame, dict[str, object]]:
    """One row per cleaned transfer, with scope/valuation/loan annotations."""
    meta: dict[str, object] = {}
    tf = t.transfers.collect()
    meta["rows_raw"] = tf.height

    tf = tf.filter(pl.col("transfer_date").is_not_null())
    meta["rows_with_date"] = tf.height
    tf = tf.sort(["player_id", "transfer_date", "from_club_id", "to_club_id"])

    n = tf.height
    tf = tf.unique(subset=["player_id", "transfer_date"], keep="first", maintain_order=True)
    meta["dupes_player_date_removed"] = n - tf.height

    n = tf.height
    tf = tf.filter(
        pl.col("from_club_id").is_null()
        | pl.col("to_club_id").is_null()
        | (pl.col("from_club_id") != pl.col("to_club_id"))
    )
    meta["self_transfers_removed"] = n - tf.height

    covered_ids, _covered_clubs = covered_club_ids(t)
    covered_list = sorted(covered_ids)
    tf = tf.with_columns(
        from_in_scope=pl.col("from_club_id").is_in(covered_list),
        to_in_scope=pl.col("to_club_id").is_in(covered_list),
        pseudo_club=(
            pl.col("from_club_name").str.contains(PSEUDO_CLUB_PATTERN).fill_null(False)
            | pl.col("to_club_name").str.contains(PSEUDO_CLUB_PATTERN).fill_null(False)
        ),
        season=season_of("transfer_date"),
    )
    tf = tf.with_columns(in_scope=pl.col("from_in_scope") & pl.col("to_in_scope"))

    # Loan probe: round-trips A->B then B->A for the same player within ~18 months.
    tf = tf.with_row_index("row_idx")
    legs = tf.select(
        "row_idx", "player_id", "transfer_date", "from_club_id", "to_club_id", "transfer_fee"
    )
    pairs = (
        legs.join(
            legs,
            left_on=["player_id", "to_club_id", "from_club_id"],
            right_on=["player_id", "from_club_id", "to_club_id"],
            how="inner",
            suffix="_ret",
        )
        .filter(pl.col("transfer_date_ret") > pl.col("transfer_date"))
        .with_columns(
            gap_days=(pl.col("transfer_date_ret") - pl.col("transfer_date")).dt.total_days()
        )
        .filter(pl.col("gap_days") <= LOAN_MAX_RETURN_DAYS)
        .sort(["gap_days", "row_idx", "row_idx_ret"])
        .unique(subset=["row_idx"], keep="first", maintain_order=True)
        .unique(subset=["row_idx_ret"], keep="first", maintain_order=True)
        .with_columns(
            pair_class=pl.when((pl.col("transfer_fee") == 0) & (pl.col("transfer_fee_ret") == 0))
            .then(pl.lit("loan"))
            .when((pl.col("transfer_fee") > 0) | (pl.col("transfer_fee_ret") > 0))
            .then(pl.lit("buyback"))
            .otherwise(pl.lit("ambiguous"))
        )
    )
    loan_pairs = pairs.filter(pl.col("pair_class") == "loan")
    loan_rows = sorted(
        set(loan_pairs["row_idx"].to_list()) | set(loan_pairs["row_idx_ret"].to_list())
    )
    tf = tf.with_columns(suspected_loan=pl.col("row_idx").is_in(loan_rows))
    meta["loan_pairs"] = loan_pairs.height
    meta["buyback_pairs"] = int(pairs.filter(pl.col("pair_class") == "buyback").height)
    meta["ambiguous_pairs"] = int(pairs.filter(pl.col("pair_class") == "ambiguous").height)
    meta["loan_rows_flagged"] = len(loan_rows)
    meta["loan_gap_days_quantiles"] = [
        int(loan_pairs["gap_days"].quantile(q) or 0) for q in (0.25, 0.5, 0.75)
    ]

    # v_before / v_after via as-of joins against the valuation history.
    vals = (
        t.valuations.select("player_id", "date", "market_value_in_eur")
        .filter(pl.col("date").is_not_null() & pl.col("market_value_in_eur").is_not_null())
        .collect()
    )
    max_val_date: date = vals["date"].max()  # type: ignore[assignment]
    meta["max_valuation_date"] = max_val_date.isoformat()

    before = vals.sort("date").rename({"date": "v_before_date", "market_value_in_eur": "v_before"})
    tf = (
        tf.with_columns(k_before=pl.col("transfer_date").dt.offset_by("-1d"))
        .sort("k_before")
        .join_asof(
            before,
            left_on="k_before",
            right_on="v_before_date",
            by="player_id",
            strategy="backward",
            tolerance=f"{V_BEFORE_MAX_DAYS - 1}d",  # window [t-180d, t-1d]: strictly before t
        )
    )
    # Same-day-inclusive variant, reported to show the leakage-avoidance cost.
    incl = (
        tf.select("row_idx", "player_id", "transfer_date")
        .sort("transfer_date")
        .join_asof(
            before,
            left_on="transfer_date",
            right_on="v_before_date",
            by="player_id",
            strategy="backward",
            tolerance=f"{V_BEFORE_MAX_DAYS}d",
        )
    )
    meta["v_before_inclusive_extra"] = int(
        incl["v_before"].is_not_null().sum() - tf["v_before"].is_not_null().sum()
    )

    after = vals.sort("date").rename({"date": "v_after_date", "market_value_in_eur": "v_after"})
    tf = (
        tf.with_columns(k_after=pl.col("transfer_date").dt.offset_by(f"{V_AFTER_MIN_DAYS}d"))
        .sort("k_after")
        .join_asof(
            after,
            left_on="k_after",
            right_on="v_after_date",
            by="player_id",
            strategy="forward",
            tolerance=f"{V_AFTER_MAX_DAYS - V_AFTER_MIN_DAYS}d",  # window [t+180d, t+540d]
        )
    )

    censor_cutoff = max_val_date - timedelta(days=V_AFTER_MIN_DAYS)
    meta["censor_cutoff"] = censor_cutoff.isoformat()
    tf = tf.with_columns(
        censored=pl.col("transfer_date") > pl.lit(censor_cutoff),
        multiplier=pl.col("v_after") / pl.col("v_before"),
    )

    # Player attributes for grid dimensions.
    players = t.players.select("player_id", "date_of_birth", "sub_position", "position").collect()
    tf = tf.join(players, on="player_id", how="left")
    tf = tf.with_columns(
        age_at_transfer=(
            (pl.col("transfer_date") - pl.col("date_of_birth")).dt.total_days() / 365.25
        ),
        pos_group=pl.col("sub_position")
        .replace_strict(POSITION_GROUPS, default=None)
        .fill_null(pl.col("position").replace_strict(COARSE_POSITION_GROUPS, default=None))
        .fill_null("UNKNOWN"),
    )
    unrecognized = (
        players.filter(
            pl.col("sub_position").is_not_null()
            & ~pl.col("sub_position").is_in(sorted(POSITION_GROUPS))
        )["sub_position"]
        .unique()
        .sort()
        .to_list()
    )
    meta["unrecognized_sub_positions"] = unrecognized

    tf = tf.drop("k_before", "k_after").sort("row_idx")
    return tf, meta


def derive_preview_league_tiers(t: Tables) -> pl.DataFrame:
    """Preview-grade league tiers (1=strongest) per season from derived squad values.

    Squad value: sum over squad members of their last valuation within the season,
    attributed to the club the valuation row carries. League membership uses the
    clubs.csv snapshot (known drift for relegated clubs - preview only).
    """
    vals = (
        t.valuations.select("player_id", "date", "market_value_in_eur", "current_club_id")
        .filter(pl.col("date").is_not_null() & pl.col("market_value_in_eur").is_not_null())
        .with_columns(season_of("date"))
        .collect()
    )
    last_in_season = (
        vals.sort("date")
        .group_by(["current_club_id", "season", "player_id"], maintain_order=True)
        .agg(pl.col("market_value_in_eur").last())
    )
    squad = last_in_season.group_by(["current_club_id", "season"], maintain_order=True).agg(
        squad_value=pl.col("market_value_in_eur").sum()
    )
    clubs = t.clubs.select("club_id", "domestic_competition_id").collect()
    league_season = (
        squad.join(clubs, left_on="current_club_id", right_on="club_id", how="inner")
        .group_by(["domestic_competition_id", "season"], maintain_order=True)
        .agg(median_squad_value=pl.col("squad_value").median(), n_clubs=pl.len())
    )
    return league_season.with_columns(
        tier=(
            (
                pl.col("median_squad_value").rank(method="ordinal", descending=True).over("season")
                - 1
            )
            * 4
            // pl.len().over("season")
            + 1
        ).cast(pl.Int8)
    ).sort(["season", "tier", "domestic_competition_id"])


def _pct(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%" if denominator else "n/a"


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def normalize_club_name(name: str) -> str:
    lowered = name.lower().translate(_TRANSLIT)
    ascii_name = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^a-z0-9 ]", " ", ascii_name)
    tokens = [t for t in ascii_name.split() if t not in _STOP_TOKENS and not t.isdigit()]
    return " ".join(tokens)


def _tokens_prefix_match(elo_tokens: frozenset[str], tm_tokens: frozenset[str]) -> bool:
    """True when every Elo token matches a TM token exactly or as a >=3-char prefix."""

    def hit(elo_tok: str) -> bool:
        return any(
            elo_tok == tm_tok
            or (len(elo_tok) >= 3 and tm_tok.startswith(elo_tok))
            or (len(tm_tok) >= 3 and elo_tok.startswith(tm_tok))
            for tm_tok in tm_tokens
        )

    return bool(elo_tokens) and all(hit(tok) for tok in elo_tokens)


def _acronyms(tokens: list[str]) -> set[str]:
    """First-letter acronyms of every contiguous token run of length >= 2."""
    return {
        "".join(tok[0] for tok in tokens[i:j])
        for i in range(len(tokens))
        for j in range(i + 2, len(tokens) + 1)
    }


# --- sections ---------------------------------------------------------------


def sec_gates(ctx: AuditContext) -> SectionResult:
    t = ctx.tables
    n_transfers = t.transfers.select(pl.len()).collect().item()
    n_valuations = t.valuations.select(pl.len()).collect().item()
    n_players = t.players.select(pl.len()).collect().item()
    n_appearances = t.appearances.select(pl.len()).collect().item()
    n_games = t.games.select(pl.len()).collect().item()
    player_cols = t.players.collect_schema().names()
    max_val_date = t.valuations.select(pl.col("date").max()).collect().item()
    min_val_date = t.valuations.select(pl.col("date").min()).collect().item()

    gates = [
        Gate(
            "transfers_min_rows",
            n_transfers >= GATE_MIN_TRANSFERS,
            f"{n_transfers:,} rows (gate: >= {GATE_MIN_TRANSFERS:,})",
        ),
        Gate(
            "valuations_min_rows",
            n_valuations >= GATE_MIN_VALUATIONS,
            f"{n_valuations:,} rows (gate: >= {GATE_MIN_VALUATIONS:,})",
        ),
        Gate(
            "players_min_rows",
            n_players >= GATE_MIN_PLAYERS,
            f"{n_players:,} rows (gate: >= {GATE_MIN_PLAYERS:,})",
        ),
        Gate(
            "players_schema",
            len(player_cols) == GATE_PLAYERS_COLUMNS and "international_caps" in player_cols,
            f"{len(player_cols)} columns, international_caps "
            f"{'present' if 'international_caps' in player_cols else 'MISSING'}",
        ),
    ]
    lines = [
        f"- transfers.csv: {n_transfers:,} rows",
        f"- player_valuations.csv: {n_valuations:,} rows, dates {min_val_date} .. {max_val_date}",
        f"- players.csv: {n_players:,} rows, {len(player_cols)} columns",
        f"- appearances.csv: {n_appearances:,} rows; games.csv: {n_games:,} rows",
        f"- VALUE FRESHNESS CUT-OFF: max(player_valuations.date) = {max_val_date} "
        "(must be surfaced in the UI as the values' as-of date)",
    ]
    metrics: dict[str, object] = {
        "transfers_rows": n_transfers,
        "valuations_rows": n_valuations,
        "players_rows": n_players,
        "appearances_rows": n_appearances,
        "games_rows": n_games,
        "players_columns": player_cols,
        "max_valuation_date": str(max_val_date),
        "min_valuation_date": str(min_val_date),
    }
    return SectionResult("gates", lines, metrics, gates)


def sec_appearance_density(ctx: AuditContext) -> SectionResult:
    t = ctx.tables
    games = t.games.select("game_id", "competition_id", "season").collect()
    apps = t.appearances.select("game_id").collect()
    per_game = apps.group_by("game_id").agg(n_apps=pl.len())
    game_apps = games.join(per_game, on="game_id", how="left").with_columns(
        pl.col("n_apps").fill_null(0)
    )
    density = (
        game_apps.group_by(["competition_id", "season"], maintain_order=True)
        .agg(n_games=pl.len(), apps_per_game=pl.col("n_apps").mean())
        .sort(["competition_id", "season"])
    )
    # Competitions whose match data only starts recently dilute per-season averages;
    # split them out ("added_2024") from the long-covered set ("legacy").
    first_season = games.group_by("competition_id").agg(first=pl.col("season").min())
    per_season = (
        game_apps.join(first_season, on="competition_id")
        .with_columns(
            cohort=pl.when(pl.col("first") <= 2015)
            .then(pl.lit("legacy"))
            .otherwise(pl.lit("added_2024"))
        )
        .group_by(["season", "cohort"], maintain_order=True)
        .agg(
            n_games=pl.len(),
            apps_per_game=pl.col("n_apps").mean(),
            zero_share=(pl.col("n_apps") == 0).mean(),
        )
        .sort(["season", "cohort"])
    )
    # Regression detector: season-competition density far below that competition's median.
    with_median = density.with_columns(
        comp_median=pl.col("apps_per_game").median().over("competition_id")
    ).filter(
        (pl.col("apps_per_game") < 0.85 * pl.col("comp_median"))
        & (pl.col("n_games") >= 50)
        & (pl.col("season") >= 2013)
    )
    lines = ["Appearance rows per game, per season and competition cohort:", "```"]
    lines += [
        f"  {row['season']} {row['cohort']:<10}: games={row['n_games']:>6,}"
        f"  apps/game={row['apps_per_game']:.1f}  games-with-0-apps={row['zero_share']:.0%}"
        for row in per_season.iter_rows(named=True)
        if row["season"] >= 2012
    ]
    lines.append("```")
    comps = t.competitions.select("competition_id", "type").collect()
    domestic = set(comps.filter(pl.col("type") == "domestic_league")["competition_id"].to_list())
    late_starters = set(first_season.filter(pl.col("first") >= 2020)["competition_id"].to_list())
    late_leagues = sorted((late_starters & domestic) - set(NEW_LEAGUES))
    lines.append(
        "European domestic leagues whose MATCH data only starts 2024 in this build"
        f" (transfers/valuations go further back): {', '.join(late_leagues) or 'none'}"
    )
    flagged = [
        f"  {row['competition_id']} {row['season']}: {row['apps_per_game']:.1f} vs "
        f"competition median {row['comp_median']:.1f} ({row['n_games']} games)"
        for row in with_median.sort(["competition_id", "season"]).iter_rows(named=True)
    ]
    lines.append(f"Season-competitions >15% below their competition median: {len(flagged)}")
    lines += flagged[:20]

    new_league_rows: list[str] = []
    new_league_metrics: dict[str, object] = {}
    for comp in NEW_LEAGUES:
        comp_density = density.filter(pl.col("competition_id") == comp)
        if comp_density.height == 0:
            new_league_rows.append(f"  {comp}: no games in this build")
            new_league_metrics[comp] = None
            continue
        seasons = comp_density["season"].to_list()
        total_games = int(comp_density["n_games"].sum())
        new_league_rows.append(
            f"  {comp}: seasons {min(seasons)}..{max(seasons)} ({len(seasons)} seasons), "
            f"{total_games:,} games"
        )
        new_league_metrics[comp] = {
            "first_season": min(seasons),
            "last_season": max(seasons),
            "n_seasons": len(seasons),
            "n_games": total_games,
        }
    lines.append("Newly added non-European leagues (backfill depth):")
    lines += new_league_rows

    metrics: dict[str, object] = {
        "apps_per_game_by_season_cohort": {
            f"{row['season']}_{row['cohort']}": {
                "n_games": row["n_games"],
                "apps_per_game": round(row["apps_per_game"], 2),
                "zero_share": round(row["zero_share"], 4),
            }
            for row in per_season.iter_rows(named=True)
        },
        "low_density_flags": with_median.height,
        "late_start_european_leagues": late_leagues,
        "new_leagues": new_league_metrics,
    }
    return SectionResult("appearance_density", lines, metrics)


def sec_funnel(ctx: AuditContext) -> SectionResult:
    tf, meta = ctx.funnel()
    rows_raw = int(meta["rows_raw"])  # type: ignore[arg-type]
    cleaned = tf.height
    in_scope = tf.filter(pl.col("in_scope"))
    out_of_scope = cleaned - in_scope.height
    pseudo = int(tf.filter(~pl.col("in_scope") & pl.col("pseudo_club")).height)
    from_only = int(tf.filter(pl.col("from_in_scope") & ~pl.col("to_in_scope")).height)
    to_only = int(tf.filter(~pl.col("from_in_scope") & pl.col("to_in_scope")).height)
    neither = out_of_scope - from_only - to_only

    with_before = in_scope.filter(pl.col("v_before").is_not_null())
    observable = with_before.filter(~pl.col("censored"))
    censored = with_before.height - observable.height
    with_both = observable.filter(pl.col("v_after").is_not_null())
    usable = with_both.filter(~pl.col("suspected_loan"))

    lines = [
        "Feasibility funnel (each stage nested in the previous):",
        "```",
        f"  raw transfer rows                 {rows_raw:>9,}",
        f"  cleaned (dated, deduped, no self) {cleaned:>9,}"
        f"  [-{int(meta['dupes_player_date_removed']):,} dupes,"  # type: ignore[arg-type]
        f" -{int(meta['self_transfers_removed']):,} self]",  # type: ignore[arg-type]
        f"  in scope (both clubs covered)     {in_scope.height:>9,}"
        f"  ({_pct(in_scope.height, cleaned)})",
        f"    out of scope                    {out_of_scope:>9,}"
        f"  [leaving coverage: {from_only:,}; entering: {to_only:,};"
        f" neither side covered: {neither:,}; pseudo-club moves: {pseudo:,}]",
        f"  with v_before (<=180d, strict)    {with_before.height:>9,}"
        f"  ({_pct(with_before.height, in_scope.height)} of in-scope)",
        f"  observable for v_after            {observable.height:>9,}"
        f"  [transfer <= {meta['censor_cutoff']}; censored: {censored:,}]",
        f"  with v_after [180,540]d           {with_both.height:>9,}"
        f"  ({_pct(with_both.height, observable.height)} of observable)",
        f"  minus suspected loans             {usable.height:>9,}"
        f"  [-{with_both.height - usable.height:,}]  <- THE COMPS UNIVERSE",
        "```",
        f"Same-day valuations excluded by the strict v_before rule: "
        f"{meta['v_before_inclusive_extra']:,} transfers would gain a v_before if the "
        "transfer-day valuation were allowed (leakage risk - kept strict).",
        "Usable transitions per season (last 15):",
        "```",
    ]
    per_season = (
        usable.group_by("season", maintain_order=True).agg(n=pl.len()).sort("season").tail(15)
    )
    lines += [f"  {row['season']}: {row['n']:>6,}" for row in per_season.iter_rows(named=True)]
    lines.append("```")

    metrics: dict[str, object] = {
        "rows_raw": rows_raw,
        "rows_cleaned": cleaned,
        "dupes_removed": meta["dupes_player_date_removed"],
        "self_transfers_removed": meta["self_transfers_removed"],
        "in_scope": in_scope.height,
        "in_scope_share": _ratio(in_scope.height, cleaned),
        "out_of_scope_from_only": from_only,
        "out_of_scope_to_only": to_only,
        "out_of_scope_neither": neither,
        "out_of_scope_pseudo_club": pseudo,
        "with_v_before": with_before.height,
        "v_before_share_of_in_scope": _ratio(with_before.height, in_scope.height),
        "v_before_inclusive_extra": meta["v_before_inclusive_extra"],
        "censor_cutoff": meta["censor_cutoff"],
        "censored": censored,
        "observable": observable.height,
        "with_v_after": with_both.height,
        "v_after_share_of_observable": _ratio(with_both.height, observable.height),
        "suspected_loans_in_universe": with_both.height - usable.height,
        "usable_transitions": usable.height,
        "usable_by_season": {
            str(row["season"]): row["n"] for row in per_season.iter_rows(named=True)
        },
    }
    return SectionResult("funnel", lines, metrics)


def sec_loan_probe(ctx: AuditContext) -> SectionResult:
    tf, meta = ctx.funnel()
    fee_zero = int(tf.filter(pl.col("transfer_fee") == 0).height)
    fee_null = int(tf.filter(pl.col("transfer_fee").is_null()).height)
    fee_pos = tf.height - fee_zero - fee_null
    loan_rows = int(meta["loan_rows_flagged"])  # type: ignore[arg-type]
    q25, q50, q75 = meta["loan_gap_days_quantiles"]  # type: ignore[misc]

    lines = [
        f"Fee coding in cleaned transfers: zero={fee_zero:,} ({_pct(fee_zero, tf.height)}), "
        f"positive={fee_pos:,}, null(unknown)={fee_null:,}.",
        "Loans carry NO flag upstream and parse to fee=0, identically to free transfers;"
        " they are detected structurally as round-trips.",
        f"Round-trip pairs (A->B then B->A within {LOAN_MAX_RETURN_DAYS}d, greedy 1:1 by"
        f" shortest gap): loan(both fees 0)={meta['loan_pairs']:,},"
        f" buyback(any fee>0)={meta['buyback_pairs']:,},"
        f" ambiguous(fee unknown)={meta['ambiguous_pairs']:,}.",
        f"Rows flagged suspected_loan (both legs of loan pairs): {loan_rows:,} "
        f"({_pct(loan_rows, tf.height)} of cleaned; {_pct(loan_rows, fee_zero)} of fee-zero).",
        f"Return-gap days for loan pairs: p25={q25}, p50={q50}, p75={q75}.",
        "PROPOSED RULE: exclude both legs of round-trips where both fees are exactly 0;"
        " keep fee>0 round-trips (buy-backs are real transfers); leave fee-null round-trips"
        " in (counted above as ambiguous). Loans converted to permanent moves never round-trip"
        " and stay invisible to this rule - documented residual contamination.",
    ]
    metrics: dict[str, object] = {
        "fee_zero": fee_zero,
        "fee_positive": fee_pos,
        "fee_null": fee_null,
        "loan_pairs": meta["loan_pairs"],
        "buyback_pairs": meta["buyback_pairs"],
        "ambiguous_pairs": meta["ambiguous_pairs"],
        "loan_rows_flagged": loan_rows,
        "loan_share_of_fee_zero": _ratio(loan_rows, fee_zero),
        "loan_gap_days_quantiles": meta["loan_gap_days_quantiles"],
    }
    return SectionResult("loan_probe", lines, metrics)


def sec_valuation_cadence(ctx: AuditContext) -> SectionResult:
    t = ctx.tables
    vals = (
        t.valuations.select("player_id", "date", "market_value_in_eur")
        .filter(pl.col("date").is_not_null())
        .with_columns(year=pl.col("date").dt.year())
        .collect()
    )
    per_player_year = vals.group_by(["player_id", "year"]).agg(n=pl.len())

    def era_stats(frame: pl.DataFrame) -> dict[str, float]:
        if frame.height == 0:
            return {"p25": 0.0, "p50": 0.0, "p75": 0.0, "share_2plus": 0.0}
        return {
            "p25": float(frame["n"].quantile(0.25) or 0),
            "p50": float(frame["n"].quantile(0.5) or 0),
            "p75": float(frame["n"].quantile(0.75) or 0),
            "share_2plus": round(float((frame["n"] >= 2).mean()), 4),
        }

    eras = {
        "2000-2011": era_stats(per_player_year.filter(pl.col("year") <= 2011)),
        "2012-2019": era_stats(
            per_player_year.filter((pl.col("year") >= 2012) & (pl.col("year") <= 2019))
        ),
        "2020+": era_stats(per_player_year.filter(pl.col("year") >= 2020)),
    }
    value_q = {
        f"p{int(q * 100)}": int(vals["market_value_in_eur"].quantile(q) or 0)
        for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)
    }
    lines = ["Valuation updates per player-year (quantiles; share of years with >=2 updates):"]
    lines += [
        f"  {era}: p25={s['p25']:.0f} p50={s['p50']:.0f} p75={s['p75']:.0f}"
        f" share_2plus={s['share_2plus']:.0%}"
        for era, s in eras.items()
    ]
    lines.append(
        "Market value distribution (EUR, all rows): "
        + ", ".join(f"{k}={v:,}" for k, v in value_q.items())
    )
    return SectionResult(
        "valuation_cadence",
        lines,
        {"updates_per_player_year": eras, "value_quantiles_eur": value_q},
    )


def sec_league_scope(ctx: AuditContext) -> SectionResult:
    t = ctx.tables
    tf, _ = ctx.funnel()
    usable = tf.filter(
        pl.col("in_scope")
        & pl.col("v_before").is_not_null()
        & pl.col("v_after").is_not_null()
        & ~pl.col("censored")
        & ~pl.col("suspected_loan")
    )
    clubs = t.clubs.select("club_id", "domestic_competition_id").collect()
    comps = (
        t.competitions.filter(pl.col("type") == "domestic_league")
        .select("competition_id", "name", "country_name")
        .collect()
    )
    to_league = (
        usable.join(clubs, left_on="to_club_id", right_on="club_id", how="inner")
        .group_by("domestic_competition_id")
        .agg(usable_in=pl.len())
    )
    from_league = (
        usable.join(clubs, left_on="from_club_id", right_on="club_id", how="inner")
        .group_by("domestic_competition_id")
        .agg(usable_out=pl.len())
    )
    games = t.games.select("competition_id", "season").collect()
    seasons = games.group_by("competition_id").agg(
        first_season=pl.col("season").min(), last_season=pl.col("season").max()
    )
    club_counts = clubs.group_by("domestic_competition_id").agg(n_clubs=pl.len())

    table = (
        comps.join(to_league, left_on="competition_id", right_on="domestic_competition_id")
        .join(
            from_league,
            left_on="competition_id",
            right_on="domestic_competition_id",
            how="left",
        )
        .join(club_counts, left_on="competition_id", right_on="domestic_competition_id")
        .join(seasons, on="competition_id", how="left")
        .with_columns(pl.col("usable_out").fill_null(0))
        .sort("usable_in", descending=True)
    )
    lines = [
        "Per covered domestic league: usable transitions in/out, clubs, game seasons:",
        "```",
        f"  {'league':<6} {'country':<14} {'in':>6} {'out':>6} {'clubs':>5}  seasons",
    ]
    lines += [
        f"  {row['competition_id']:<6} {(row['country_name'] or '-')[:14]:<14}"
        f" {row['usable_in']:>6,} {row['usable_out']:>6,} {row['n_clubs']:>5}"
        f"  {row['first_season']}-{row['last_season']}"
        for row in table.iter_rows(named=True)
    ]
    lines.append("```")
    metrics: dict[str, object] = {
        "leagues": {
            str(row["competition_id"]): {
                "country": row["country_name"],
                "usable_in": row["usable_in"],
                "usable_out": row["usable_out"],
                "n_clubs": row["n_clubs"],
                "first_season": row["first_season"],
                "last_season": row["last_season"],
            }
            for row in table.iter_rows(named=True)
        }
    }
    return SectionResult("league_scope", lines, metrics)


def sec_comp_pool_grid(ctx: AuditContext) -> SectionResult:
    tf, _ = ctx.funnel()
    tiers = ctx.league_tiers()
    clubs = ctx.tables.clubs.select("club_id", "domestic_competition_id").collect()

    usable = tf.filter(
        pl.col("in_scope")
        & pl.col("v_before").is_not_null()
        & pl.col("v_after").is_not_null()
        & ~pl.col("censored")
        & ~pl.col("suspected_loan")
    )
    tier_lookup = tiers.select("domestic_competition_id", "season", "tier")
    graded = (
        usable.join(
            clubs.rename({"domestic_competition_id": "from_league"}),
            left_on="from_club_id",
            right_on="club_id",
        )
        .join(
            clubs.rename({"domestic_competition_id": "to_league"}),
            left_on="to_club_id",
            right_on="club_id",
        )
        .join(
            tier_lookup.rename({"tier": "tier_from"}),
            left_on=["from_league", "season"],
            right_on=["domestic_competition_id", "season"],
            how="left",
        )
        .join(
            tier_lookup.rename({"tier": "tier_to"}),
            left_on=["to_league", "season"],
            right_on=["domestic_competition_id", "season"],
            how="left",
        )
        .with_columns(
            age_band=pl.when(pl.col("age_at_transfer") < 21)
            .then(pl.lit("U21"))
            .when(pl.col("age_at_transfer") < 25)
            .then(pl.lit("21-24"))
            .when(pl.col("age_at_transfer") < 29)
            .then(pl.lit("25-28"))
            .when(pl.col("age_at_transfer") >= 29)
            .then(pl.lit("29+"))
            .otherwise(None),
            value_bracket=pl.when(pl.col("v_before") < 1_000_000)
            .then(pl.lit("<1M"))
            .when(pl.col("v_before") < 5_000_000)
            .then(pl.lit("1-5M"))
            .when(pl.col("v_before") < 15_000_000)
            .then(pl.lit("5-15M"))
            .when(pl.col("v_before") < 40_000_000)
            .then(pl.lit("15-40M"))
            .otherwise(pl.lit(">40M")),
        )
    )
    dims = ["pos_group", "age_band", "value_bracket", "tier_from", "tier_to"]
    complete = graded.filter(
        pl.all_horizontal([pl.col(d).is_not_null() for d in dims])
        & (pl.col("pos_group") != "UNKNOWN")
    )
    cells = complete.group_by(dims, maintain_order=True).agg(n=pl.len()).sort(dims)
    weighted = complete.join(cells, on=dims, how="left")
    share_ge = {
        k: round(float((weighted["n"] >= k).mean()), 4) if weighted.height else 0.0
        for k in (5, 20, 50)
    }
    lines = [
        "Comp-pool density preview over (position group x age band x value bracket x"
        " origin tier -> destination tier). Tiers are PREVIEW-GRADE per-season quartiles"
        " of league median derived squad value (clubs.csv snapshot league membership).",
        f"- transitions with all dimensions known: {complete.height:,}"
        f" of {usable.height:,} usable ({_pct(complete.height, usable.height)})",
        f"- non-empty cells: {cells.height:,} (max possible 4x4x5x4x4 = 1,280)",
        f"- cell size: median={int(cells['n'].median() or 0)},"
        f" p90={int(cells['n'].quantile(0.9) or 0)}, max={int(cells['n'].max() or 0)}",
        f"- transition-weighted share landing in cells with >=5: {share_ge[5]:.0%},"
        f" >=20: {share_ge[20]:.0%}, >=50: {share_ge[50]:.0%}",
        "  (cells below ~5 comps are where the relaxation ladder will fire)",
    ]
    metrics: dict[str, object] = {
        "transitions_graded": complete.height,
        "usable_transitions": usable.height,
        "non_empty_cells": cells.height,
        "cell_median": int(cells["n"].median() or 0),
        "cell_p90": int(cells["n"].quantile(0.9) or 0),
        "cell_max": int(cells["n"].max() or 0),
        "weighted_share_ge": share_ge,
    }
    return SectionResult("comp_pool_grid", lines, metrics)


def sec_elo_probe(ctx: AuditContext) -> SectionResult:
    ext = ctx.external_dir
    needed = ["eloratings_bimonthly.csv", "clubelo_daily.csv", "team_mapping.csv"]
    if any(not (ext / f).exists() for f in needed):
        return SectionResult("elo_probe", ["SKIPPED: external Elo files missing"], {})

    mirror_a = pl.read_csv(ext / "eloratings_bimonthly.csv")
    mirror_b = pl.read_csv(ext / "clubelo_daily.csv", columns=["Club", "Country", "Level", "date"])
    a_dates = (str(mirror_a["date"].min()), str(mirror_a["date"].max()))
    b_dates = (str(mirror_b["date"].min()), str(mirror_b["date"].max()))
    elo_names = sorted(set(mirror_a["club"].to_list()) | set(mirror_b["Club"].unique().to_list()))
    norm_groups: dict[str, list[str]] = {}
    for name in elo_names:
        norm_groups.setdefault(normalize_club_name(name), []).append(name)
    # Normalized names shared by several distinct Elo clubs are unsafe for matching.
    norm_to_elo = {norm: names[0] for norm, names in norm_groups.items() if len(names) == 1}
    collisions = {norm: names for norm, names in norm_groups.items() if len(names) > 1}
    elo_tokens = {name: frozenset(norm.split()) for norm, name in norm_to_elo.items()}

    tf, _ = ctx.funnel()
    clubs = ctx.tables.clubs.select(
        "club_id", "name", "club_code", "domestic_competition_id"
    ).collect()
    universe = tf.filter(
        pl.col("in_scope")
        & pl.col("v_before").is_not_null()
        & pl.col("v_after").is_not_null()
        & ~pl.col("censored")
        & ~pl.col("suspected_loan")
    )
    touches = (
        pl.concat(
            [
                universe.select(club_id=pl.col("from_club_id")),
                universe.select(club_id=pl.col("to_club_id")),
            ]
        )
        .group_by("club_id")
        .agg(weight=pl.len())
    )
    weighted_clubs = touches.join(clubs, on="club_id", how="inner").sort("weight", descending=True)

    # Stage 0: reep team register carries key_transfermarkt AND key_clubelo.
    bridge: dict[int, str] = {}
    reep_teams_path = ext / "reep_teams.csv"
    if reep_teams_path.exists():
        rt = pl.read_csv(reep_teams_path, infer_schema=False).select(
            "key_transfermarkt", "key_clubelo"
        )
        rt = rt.filter(
            pl.col("key_transfermarkt").is_not_null() & pl.col("key_clubelo").is_not_null()
        ).with_columns(pl.col("key_transfermarkt").cast(pl.Int64, strict=False))
        bridge = {
            int(row["key_transfermarkt"]): str(row["key_clubelo"])
            for row in rt.iter_rows(named=True)
            if row["key_transfermarkt"] is not None
        }

    mapping_csv = pl.read_csv(ext / "team_mapping.csv").filter(pl.col("team_clubelo").is_not_null())
    opta_to_elo = {
        normalize_club_name(str(row["team_opta"])): str(row["team_clubelo"])
        for row in mapping_csv.iter_rows(named=True)
    }

    mapped: dict[int, tuple[str, str]] = {}  # club_id -> (elo name, stage)
    for row in weighted_clubs.iter_rows(named=True):
        club_id = int(row["club_id"])
        # Two name candidates: the (often legal) club name and the URL slug,
        # which tends to carry the common short name ("psv-eindhoven").
        candidates = [normalize_club_name(str(row["name"]))]
        if row["club_code"]:
            code_norm = normalize_club_name(str(row["club_code"]).replace("-", " "))
            if code_norm and code_norm not in candidates:
                candidates.append(code_norm)

        hit: tuple[str, str] | None = None
        if club_id in bridge and normalize_club_name(bridge[club_id]) in norm_groups:
            hit = (bridge[club_id], "0_reep_id_bridge")
        for norm in candidates if hit is None else []:
            if norm in norm_to_elo:
                hit = (norm_to_elo[norm], "1_exact_normalized")
                break
        if hit is None:
            for stage_name, matcher in (
                (
                    "2_token_subset",
                    lambda et, tm: bool(et) and (et <= tm or tm <= et),
                ),
                ("3_token_prefix", _tokens_prefix_match),
            ):
                stage_hits = {
                    name
                    for norm in candidates
                    for name, etoks in elo_tokens.items()
                    if matcher(etoks, frozenset(norm.split()))
                }
                if len(stage_hits) == 1:
                    hit = (next(iter(stage_hits)), stage_name)
                    break
        if hit is None:
            acronyms = {a for norm in candidates for a in _acronyms(norm.split())}
            acro_hits = {
                name
                for name, etoks in elo_tokens.items()
                if len(etoks) == 1 and next(iter(etoks)) in acronyms
            }
            if len(acro_hits) == 1:
                hit = (next(iter(acro_hits)), "4_acronym")
        if hit is None:
            for norm in candidates:
                if norm in opta_to_elo:
                    hit = (opta_to_elo[norm], "5_team_mapping")
                    break
        if hit is None:
            close = difflib.get_close_matches(candidates[0], sorted(norm_to_elo), n=1, cutoff=0.85)
            if close:
                hit = (norm_to_elo[close[0]], "6_difflib")
        if hit is not None:
            mapped[club_id] = hit

    total_w = int(weighted_clubs["weight"].sum())
    stage_w: dict[str, int] = {}
    for row in weighted_clubs.iter_rows(named=True):
        stage = mapped.get(int(row["club_id"]), (None, "unmapped"))[1]
        stage_w[stage] = stage_w.get(stage, 0) + int(row["weight"])
    mapped_w = total_w - stage_w.get("unmapped", 0)

    per_league = (
        weighted_clubs.with_columns(
            is_mapped=pl.col("club_id").is_in(sorted(mapped)),
        )
        .group_by("domestic_competition_id", maintain_order=True)
        .agg(
            weight=pl.col("weight").sum(),
            mapped_weight=pl.col("weight").filter(pl.col("is_mapped")).sum().fill_null(0),
        )
        .with_columns(coverage=pl.col("mapped_weight") / pl.col("weight"))
        .sort("weight", descending=True)
    )
    unmapped_top = weighted_clubs.filter(~pl.col("club_id").is_in(sorted(mapped))).head(20)

    lines = [
        f"Mirror A (bi-monthly): {a_dates[0]}..{a_dates[1]},"
        f" {mirror_a['club'].n_unique():,} clubs, {mirror_a['country'].n_unique()} countries.",
        f"Mirror B (daily): {b_dates[0]}..{b_dates[1]},"
        f" {mirror_b['Club'].n_unique():,} clubs, {mirror_b['Country'].n_unique()} countries.",
        f"Comps-universe clubs: {weighted_clubs.height:,} ({total_w:,} transition touches).",
        f"reep TM<->ClubElo id-bridge entries: {len(bridge):,};"
        f" ambiguous normalized Elo names excluded from auto-match: {len(collisions)}.",
        "Transition-weighted mapping coverage by stage:",
    ]
    lines += [f"  {stage}: {_pct(w, total_w)}" for stage, w in sorted(stage_w.items())]
    lines.append(
        f"TOTAL mapped: {_pct(mapped_w, total_w)} of transition touches"
        f" ({len(mapped):,}/{weighted_clubs.height:,} clubs)."
    )
    lines.append("Per-league coverage (weighted, worst 10 of the top-30 by volume):")
    worst = per_league.head(30).sort("coverage").head(10)
    lines += [
        f"  {row['domestic_competition_id']}: {row['coverage']:.0%} of {row['weight']:,} touches"
        for row in worst.iter_rows(named=True)
    ]
    lines.append("Top unmapped clubs by transition volume:")
    lines += [
        f"  {row['name']} ({row['domestic_competition_id']}): {row['weight']:,} touches"
        for row in unmapped_top.iter_rows(named=True)
    ]
    lines.append(
        "Structural gap: ClubElo covers UEFA countries only - the newly added"
        " non-European leagues can never map; their share shows in the per-league table."
    )
    metrics: dict[str, object] = {
        "mirror_a": {
            "dates": a_dates,
            "clubs": mirror_a["club"].n_unique(),
            "countries": mirror_a["country"].n_unique(),
        },
        "mirror_b": {
            "dates": b_dates,
            "clubs": mirror_b["Club"].n_unique(),
            "countries": mirror_b["Country"].n_unique(),
        },
        "universe_clubs": weighted_clubs.height,
        "transition_touches": total_w,
        "reep_bridge_size": len(bridge),
        "norm_collisions": len(collisions),
        "stage_weights": dict(sorted(stage_w.items())),
        "weighted_coverage": _ratio(mapped_w, total_w),
        "clubs_mapped": len(mapped),
        "per_league_coverage": {
            str(row["domestic_competition_id"]): round(float(row["coverage"]), 4)
            for row in per_league.iter_rows(named=True)
        },
        "top_unmapped": [
            {
                "name": row["name"],
                "league": row["domestic_competition_id"],
                "touches": row["weight"],
            }
            for row in unmapped_top.iter_rows(named=True)
        ],
    }
    return SectionResult("elo_probe", lines, metrics)


def sec_reep_audit(ctx: AuditContext) -> SectionResult:
    path = ctx.external_dir / "reep_people.csv"
    if not path.exists():
        return SectionResult("reep_audit", ["SKIPPED: reep_people.csv missing"], {})

    people = pl.read_csv(path, infer_schema=False)
    key_cols = [c for c in people.columns if c.startswith("key_")]
    people = people.with_columns(tm_id=pl.col("key_transfermarkt").cast(pl.Int64, strict=False))
    with_tm = people.filter(pl.col("tm_id").is_not_null())
    dup_tm = with_tm.height - with_tm["tm_id"].n_unique()

    tf, _ = ctx.funnel()
    universe_players = tf.filter(pl.col("in_scope")).select("player_id").unique().sort("player_id")
    joined = universe_players.join(with_tm, left_on="player_id", right_on="tm_id", how="left")
    matched = joined.filter(pl.col("reep_id").is_not_null())
    fill_rates = sorted(
        (
            (col, int(matched[col].is_not_null().sum()))
            for col in key_cols
            if col != "key_transfermarkt"
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    lines = [
        f"reep people: {people.height:,} rows; key_transfermarkt present on"
        f" {with_tm.height:,} ({dup_tm:,} duplicate TM ids).",
        f"In-scope transfer players matched by TM id: {matched.height:,}"
        f" / {universe_players.height:,} ({_pct(matched.height, universe_players.height)}).",
        "Fill rates among matched players (top 15 provider keys):",
    ]
    lines += [f"  {col}: {n:,} ({_pct(n, matched.height)})" for col, n in fill_rates[:15]]
    lines.append(
        "NOTE: key_sofifa holds legacy fifa.com archive IDs (Wikidata P1469), NOT SoFIFA"
        " site IDs - it must not be used as a Transfermarkt<->SoFIFA join. reep's value"
        " here: TM-id-keyed bridges to FBref/Understat/etc, and the teams register's"
        " key_clubelo bridge used by the Elo probe."
    )
    metrics: dict[str, object] = {
        "people_rows": people.height,
        "with_key_transfermarkt": with_tm.height,
        "duplicate_tm_ids": dup_tm,
        "universe_players": universe_players.height,
        "matched_players": matched.height,
        "match_share": _ratio(matched.height, universe_players.height),
        "fill_rates_matched": dict(fill_rates),
    }
    return SectionResult("reep_audit", lines, metrics)


SECTIONS: dict[str, object] = {
    "gates": sec_gates,
    "appearance_density": sec_appearance_density,
    "valuation_cadence": sec_valuation_cadence,
    "funnel": sec_funnel,
    "loan_probe": sec_loan_probe,
    "league_scope": sec_league_scope,
    "comp_pool_grid": sec_comp_pool_grid,
    "elo_probe": sec_elo_probe,
    "reep_audit": sec_reep_audit,
}


# --- report assembly ---------------------------------------------------------


def render_markdown(results: list[SectionResult], source_line: str) -> str:
    all_gates = [g for r in results for g in r.gates]
    lines = ["# Raw data audit report", "", source_line, "", "## Gates", ""]
    lines += [f"- {'PASS' if g.passed else 'FAIL'} `{g.name}`: {g.detail}" for g in all_gates] or [
        "- (gates section not run)"
    ]
    for result in results:
        lines += ["", f"## {result.name}", ""]
        lines += result.lines
    return "\n".join(lines) + "\n"


def render_json(results: list[SectionResult]) -> str:
    payload = {
        result.name: {
            "metrics": result.metrics,
            "gates": [
                {"name": g.name, "passed": g.passed, "detail": g.detail} for g in result.gates
            ],
        }
        for result in results
    }
    return json.dumps(payload, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # windows console default
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR_DEFAULT)
    parser.add_argument(
        "--sections",
        default="all",
        help="comma-separated subset of: " + ",".join(SECTIONS),
    )
    args = parser.parse_args(argv)

    wanted = list(SECTIONS) if args.sections == "all" else args.sections.split(",")
    unknown = [s for s in wanted if s not in SECTIONS]
    if unknown:
        parser.error(f"unknown sections: {unknown}")

    manifest_path = args.raw_dir / "MANIFEST.json"
    source_line = "Source: (no MANIFEST.json found)"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        source_line = f"Source: `{json.dumps(manifest.get('tables_source', {}))}`"

    ctx = AuditContext(raw_dir=args.raw_dir, tables=load_tables(args.raw_dir))
    results: list[SectionResult] = []
    for name in wanted:
        print(f"[explore] running section: {name}", file=sys.stderr)
        section = SECTIONS[name]
        results.append(section(ctx))  # type: ignore[operator]

    report_md = render_markdown(results, source_line)
    out_dir = args.raw_dir / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit_report.md").write_text(report_md, encoding="utf-8")
    (out_dir / "audit_report.json").write_text(render_json(results), encoding="utf-8")
    print(report_md)
    print(f"[explore] wrote {out_dir / 'audit_report.md'} and audit_report.json", file=sys.stderr)

    failed = [g for r in results for g in r.gates if not g.passed]
    if failed:
        print(f"[explore] GATE FAILURES: {[g.name for g in failed]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
