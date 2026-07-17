"""CLI for the temporal backtest: uv run python -m pipeline.eval <stage>.

All filesystem writes live here (mirroring build.py's io discipline);
stages are pure functions over frames. Outputs land in data/eval/
(gitignored) - the committed deliverable is docs/eval-report.md.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import polars as pl

from app.repositories.store import load_store
from pipeline.config import PROCESSED_DIR_DEFAULT, SERVER_DIR
from pipeline.eval.metrics import aggregate
from pipeline.eval.runner import run_backtest
from pipeline.eval.splits import TEST_SEASONS, VALIDATION_SEASONS

EVAL_DIR_DEFAULT = SERVER_DIR / "data" / "eval"


def _utf8_stdout() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")


def _print_frame(frame: pl.DataFrame) -> None:
    with pl.Config(tbl_cols=-1, tbl_rows=-1, tbl_width_chars=200, float_precision=4):
        print(frame)


def _cmd_backtest(args: argparse.Namespace) -> int:
    store = load_store(args.data_dir)
    seasons = VALIDATION_SEASONS if args.phase == "validation" else TEST_SEASONS
    if args.phase == "test":
        print("NOTE: test seasons are scored exactly once, after the tuning freeze.")
    records, skips = run_backtest(store, seasons, club_level=args.dest_level == "club")

    args.eval_dir.mkdir(parents=True, exist_ok=True)
    records_path = args.eval_dir / f"records_{args.phase}_{args.tag}.parquet"
    records.write_parquet(records_path)
    skips_payload = {
        "n_skipped": len(skips),
        "by_reason": dict(sorted(Counter(s.reason for s in skips).items())),
        "skipped": [asdict(s) for s in skips],
    }
    skips_path = args.eval_dir / f"skips_{args.phase}_{args.tag}.json"
    skips_path.write_text(json.dumps(skips_payload, indent=2, default=str), encoding="utf-8")

    print(
        f"phase={args.phase} tag={args.tag} dest_level={args.dest_level} "
        f"records={records.height} skipped={len(skips)}"
    )
    print(f"-> {records_path}")
    _print_frame(aggregate(records, []))
    _print_frame(aggregate(records, ["season"], min_cell=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(prog="python -m pipeline.eval", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROCESSED_DIR_DEFAULT)
    parser.add_argument("--eval-dir", type=Path, default=EVAL_DIR_DEFAULT)
    subparsers = parser.add_subparsers(dest="stage", required=True)

    backtest = subparsers.add_parser("backtest", help="real-service backtest for one phase")
    backtest.add_argument("--phase", choices=("validation", "test"), default="validation")
    backtest.add_argument("--dest-level", choices=("club", "league"), default="club")
    backtest.add_argument("--tag", default="handset", help="suffix for output filenames")
    backtest.set_defaults(func=_cmd_backtest)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
