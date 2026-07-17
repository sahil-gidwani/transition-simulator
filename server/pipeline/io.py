"""All file I/O for the pipeline: raw tables, manifest, external files, artifacts.

Nothing outside this module (and build.py, which orchestrates it) touches the
filesystem; transforms are pure. Raw tables are scanned exactly like the audit
script so the funnel parity gate compares like with like.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class RawTables:
    players: pl.LazyFrame
    valuations: pl.LazyFrame
    transfers: pl.LazyFrame
    appearances: pl.LazyFrame
    clubs: pl.LazyFrame
    competitions: pl.LazyFrame
    games: pl.LazyFrame
    club_games: pl.LazyFrame


@dataclass(frozen=True)
class TablesSource:
    source: str
    repo: str | None
    revision: str | None


@dataclass(frozen=True)
class ArtifactInfo:
    name: str
    rows: int
    n_bytes: int
    sha256: str


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


def load_raw(raw_dir: Path) -> RawTables:
    def scan(name: str) -> pl.LazyFrame:
        return pl.scan_csv(raw_dir / name, try_parse_dates=True, infer_schema_length=10_000)

    return RawTables(
        players=_ensure_date(scan("players.csv"), ["date_of_birth"]),
        valuations=_ensure_date(scan("player_valuations.csv"), ["date"]),
        transfers=_ensure_date(scan("transfers.csv"), ["transfer_date"]),
        appearances=_ensure_date(scan("appearances.csv"), ["date"]),
        clubs=scan("clubs.csv"),
        competitions=scan("competitions.csv"),
        games=_ensure_date(scan("games.csv"), ["date"]),
        club_games=scan("club_games.csv"),
    )


def read_manifest(raw_dir: Path) -> TablesSource | None:
    path = raw_dir / "MANIFEST.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    source = payload.get("tables_source", {})
    if not isinstance(source, dict):
        return None
    return TablesSource(
        source=str(source.get("source", "")),
        repo=str(source["repo"]) if "repo" in source else None,
        revision=str(source["revision"]) if "revision" in source else None,
    )


def load_elo_mirrors(raw_dir: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(bimonthly, daily) mirrors with harmonized columns: elo_name, snapshot_date, elo.

    The daily mirror's snapshot date is its capture column `date`; duplicate
    (club, capture) rows keep the freshest `updated_at` (ISO strings, so the
    lexicographic max is the chronological max).
    """
    ext = raw_dir / "external"
    bimonthly = (
        pl.read_csv(ext / "eloratings_bimonthly.csv")
        .select(
            elo_name=pl.col("club"),
            snapshot_date=pl.col("date").cast(pl.String).str.to_date(),
            elo=pl.col("elo").cast(pl.Float64),
        )
        .drop_nulls(["elo_name", "snapshot_date", "elo"])
    )
    daily = (
        pl.read_csv(
            ext / "clubelo_daily.csv",
            columns=["Club", "Elo", "date", "updated_at"],
            schema_overrides={"Club": pl.String, "Elo": pl.Float64, "updated_at": pl.String},
        )
        .drop_nulls(["Club", "date", "Elo"])
        .sort(["Club", "date", "updated_at"])
        .unique(subset=["Club", "date"], keep="last", maintain_order=True)
        .select(
            elo_name=pl.col("Club"),
            snapshot_date=pl.col("date").cast(pl.String).str.to_date(),
            elo=pl.col("Elo"),
        )
    )
    return bimonthly, daily


def load_reep_team_bridge(raw_dir: Path) -> dict[int, str]:
    """key_transfermarkt -> key_clubelo from the reep team register (stage 0)."""
    path = raw_dir / "external" / "reep_teams.csv"
    if not path.exists():
        return {}
    rt = (
        pl.read_csv(path, infer_schema=False)
        .select("key_transfermarkt", "key_clubelo")
        .filter(pl.col("key_transfermarkt").is_not_null() & pl.col("key_clubelo").is_not_null())
        .with_columns(pl.col("key_transfermarkt").cast(pl.Int64, strict=False))
        .filter(pl.col("key_transfermarkt").is_not_null())
    )
    return {int(row[0]): str(row[1]) for row in rt.iter_rows()}


def load_team_mapping(raw_dir: Path) -> pl.DataFrame:
    """Opta->ClubElo name pairs (ladder stage 5); empty frame when absent."""
    path = raw_dir / "external" / "team_mapping.csv"
    if not path.exists():
        return pl.DataFrame(schema={"team_opta": pl.String, "team_clubelo": pl.String})
    return (
        pl.read_csv(path, infer_schema=False)
        .select("team_opta", "team_clubelo")
        .filter(pl.col("team_clubelo").is_not_null())
    )


MANUAL_FIXES_SCHEMA: dict[str, type[pl.DataType]] = {
    "elo_name": pl.String,
    "club_id": pl.Int64,
    "tm_name": pl.String,
    "note": pl.String,
}


def load_manual_fixes(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, schema_overrides=MANUAL_FIXES_SCHEMA)


def write_artifact(df: pl.DataFrame, out_dir: Path, name: str) -> ArtifactInfo:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    df.write_parquet(path, compression="zstd", statistics=True)
    data = path.read_bytes()
    return ArtifactInfo(
        name=name, rows=df.height, n_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
    )


def write_json(payload: str, out_dir: Path, name: str) -> ArtifactInfo:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(payload, encoding="utf-8", newline="\n")
    data = path.read_bytes()
    return ArtifactInfo(
        name=name, rows=0, n_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
    )


def promote(tmp_dir: Path, out_dir: Path) -> None:
    """Move every file from the temp build dir into the output dir, then drop it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(tmp_dir.iterdir()):
        if path.is_file():
            path.replace(out_dir / path.name)
    tmp_dir.rmdir()
