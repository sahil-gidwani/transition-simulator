"""Download Precedent's raw datasets into server/data/raw/ (gitignored).

Primary tables are a transfermarkt-datasets build (12 CSV tables, CC0),
pinned to an immutable revision of the HuggingFace mirror
``ngeorgea/transfermarkt-player-scores``. Pinning matters: Kaggle builds of
``davidcariboo/player-scores`` published after 2026-05-12 ship a collapsed
transfers.csv (~40k rows instead of >150k; see discussion #374 in
dcaribou/transfermarkt-datasets), and Kaggle dataset versions carry no
immutable content identifier. The revision pinned below was gate-checked by
``scripts/explore.py`` (transfers >= 150k, among others) before being
trusted. A Kaggle download path is kept as an alternative; whichever source
is used, run the audit gates before building on top of a new vintage.

External data lands in server/data/raw/external/:
- ClubElo rating snapshots via two public mirrors (data: clubelo.com).
- team-mapping.csv from tonyelhabr/club-rankings (Opta <-> ClubElo names).
- The reep cross-provider ID register (CC0).

Usage (from server/):
    uv run --group data python scripts/download_data.py                 # everything
    uv run --group data python scripts/download_data.py --only tables
    uv run --group data python scripts/download_data.py --only external
    uv run --group data python scripts/download_data.py --source kaggle --kaggle-version 342

The Kaggle path needs KAGGLE_USERNAME / KAGGLE_KEY in the environment (see
.env.example at the repo root).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import httpx

HF_REPO = "ngeorgea/transfermarkt-player-scores"
# Upstream sync of 2026-06-29; transfers.csv = 175,043 rows (healthy build).
PINNED_HF_REVISION = "7dbc5b38ba6efdc439933b00c2f4b4a7405dd681"
KAGGLE_DATASET = "davidcariboo/player-scores"

TABLES: tuple[str, ...] = (
    "appearances.csv",
    "club_games.csv",
    "clubs.csv",
    "competitions.csv",
    "countries.csv",
    "game_events.csv",
    "game_lineups.csv",
    "games.csv",
    "national_teams.csv",
    "player_valuations.csv",
    "players.csv",
    "transfers.csv",
)

EXTERNAL_FILES: dict[str, str] = {
    "eloratings_bimonthly.csv": (
        "https://raw.githubusercontent.com/xgabora/"
        "Club-Football-Match-Data-2000-2025/main/data/EloRatings.csv"
    ),
    "clubelo_daily.csv": (
        "https://github.com/tonyelhabr/club-rankings/releases/download/"
        "club-rankings/clubelo-club-rankings.csv"
    ),
    "team_mapping.csv": (
        "https://raw.githubusercontent.com/tonyelhabr/club-rankings/master/team-mapping.csv"
    ),
    "reep_people.csv": "https://raw.githubusercontent.com/withqwerty/reep/main/data/people.csv",
    "reep_teams.csv": "https://raw.githubusercontent.com/withqwerty/reep/main/data/teams.csv",
    "reep_meta.json": "https://raw.githubusercontent.com/withqwerty/reep/main/data/meta.json",
}

RAW_DIR_DEFAULT = Path(__file__).resolve().parents[1] / "data" / "raw"


def _client() -> httpx.Client:
    # TLS trust comes from the environment (SSL_CERT_FILE / REQUESTS_CA_BUNDLE).
    return httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0, read=300.0))


def _download(client: httpx.Client, url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    written = 0
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=1 << 20):
                written += fh.write(chunk)
    tmp.replace(dest)
    print(f"  {dest.name}: {written:,} bytes")
    return written


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_tables_hf(raw_dir: Path, revision: str) -> dict[str, str]:
    base = f"https://huggingface.co/datasets/{HF_REPO}/resolve/{revision}"
    print(f"Tables from HF mirror {HF_REPO} @ {revision[:12]}")
    with _client() as client:
        for name in TABLES:
            _download(client, f"{base}/{name}", raw_dir / name)
    return {"source": "huggingface", "repo": HF_REPO, "revision": revision}


def download_tables_kaggle(raw_dir: Path, version: int | None) -> dict[str, str]:
    import kagglehub  # deferred: only the Kaggle path needs it

    handle = KAGGLE_DATASET if version is None else f"{KAGGLE_DATASET}/versions/{version}"
    print(f"Tables from Kaggle {handle} (via kagglehub)")
    src = Path(kagglehub.dataset_download(handle))
    for name in TABLES:
        found = next(iter(src.rglob(name)), None)
        if found is None:
            msg = f"{name} missing from Kaggle download at {src}"
            raise FileNotFoundError(msg)
        shutil.copy2(found, raw_dir / name)
        print(f"  {name}: {(raw_dir / name).stat().st_size:,} bytes")
    return {
        "source": "kaggle",
        "dataset": KAGGLE_DATASET,
        "version": "latest" if version is None else str(version),
    }


def download_external(raw_dir: Path) -> None:
    external_dir = raw_dir / "external"
    print("External files")
    with _client() as client:
        for name, url in EXTERNAL_FILES.items():
            _download(client, url, external_dir / name)


def write_manifest(raw_dir: Path, source: dict[str, str]) -> None:
    files: dict[str, dict[str, object]] = {}
    for path in sorted(raw_dir.rglob("*")):
        if path.is_file() and path.suffix in {".csv", ".json"} and path.name != "MANIFEST.json":
            rel = path.relative_to(raw_dir).as_posix()
            files[rel] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
    manifest = {"tables_source": source, "files": files}
    (raw_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"MANIFEST.json written ({len(files)} files)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["all", "tables", "external"], default="all")
    parser.add_argument("--source", choices=["hf", "kaggle"], default="hf")
    parser.add_argument(
        "--hf-revision",
        default=PINNED_HF_REVISION,
        help="HF mirror revision SHA (default: the pinned, gate-checked revision)",
    )
    parser.add_argument(
        "--kaggle-version",
        type=int,
        default=None,
        help="Kaggle dataset version number (default: latest — must be re-gated)",
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR_DEFAULT)
    args = parser.parse_args(argv)

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    source: dict[str, str] = {"source": "unchanged"}
    if args.only in ("all", "tables"):
        if args.source == "hf":
            source = download_tables_hf(args.raw_dir, args.hf_revision)
        else:
            source = download_tables_kaggle(args.raw_dir, args.kaggle_version)
    if args.only in ("all", "external"):
        download_external(args.raw_dir)
    write_manifest(args.raw_dir, source)
    print("Done. Next: uv run --group data python scripts/explore.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
