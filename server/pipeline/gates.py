"""Hard audit gates: pure checks that decide whether a build may be promoted.

Input gates catch a wrong or defective raw vintage before any heavy work;
output gates catch logic drift (the funnel gate is exact equality against the
audited numbers) and coverage regressions. Every gate in a phase runs before
the build fails, so a failure prints the complete picture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from pipeline.config import Expectations, FunnelCounts
from pipeline.io import TablesSource


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    expected: str
    actual: str
    detail: str = ""


def all_passed(gates: list[GateResult]) -> bool:
    return all(g.passed for g in gates)


def render_gate_table(gates: list[GateResult]) -> str:
    lines = ["| gate | status | expected | actual |", "|---|---|---|---|"]
    for g in gates:
        status = "PASS" if g.passed else "FAIL"
        actual = g.actual if not g.detail else f"{g.actual} - {g.detail}"
        lines.append(f"| {g.name} | {status} | {g.expected} | {actual} |")
    return "\n".join(lines)


def check_manifest_pin(source: TablesSource | None, repo: str, revision: str) -> GateResult:
    expected = f"huggingface {repo} @ {revision}"
    if source is None:
        return GateResult(
            "manifest_pin",
            False,
            expected,
            "MANIFEST.json missing or unreadable",
            "re-run scripts/download_data.py",
        )
    actual = f"{source.source} {source.repo or '?'} @ {source.revision or '?'}"
    passed = source.source == "huggingface" and source.repo == repo and source.revision == revision
    detail = "" if passed else "raw data is not the pinned revision; re-run the audit before use"
    return GateResult("manifest_pin", passed, expected, actual, detail)


def check_table_floors(
    n_transfers: int, n_valuations: int, n_players: int, exp: Expectations
) -> list[GateResult]:
    return [
        GateResult(
            "transfers_min_rows",
            n_transfers >= exp.min_transfers,
            f">= {exp.min_transfers:,}",
            f"{n_transfers:,}",
        ),
        GateResult(
            "valuations_min_rows",
            n_valuations >= exp.min_valuations,
            f">= {exp.min_valuations:,}",
            f"{n_valuations:,}",
        ),
        GateResult(
            "players_min_rows",
            n_players >= exp.min_players,
            f">= {exp.min_players:,}",
            f"{n_players:,}",
        ),
    ]


def check_players_schema(columns: list[str], exp: Expectations) -> GateResult:
    has_caps = "international_caps" in columns
    passed = len(columns) == exp.players_columns and has_caps
    return GateResult(
        "players_schema",
        passed,
        f"{exp.players_columns} columns incl. international_caps",
        f"{len(columns)} columns, international_caps {'present' if has_caps else 'MISSING'}",
    )


def check_valuation_freshness(measured: date, exp: Expectations) -> GateResult:
    passed = measured == exp.max_valuation_date
    detail = ""
    if measured < exp.max_valuation_date:
        detail = (
            "valuations are staler than the pinned vintage - this is the frozen-valuations "
            "defect the Kaggle distribution shipped (issue #377); do not trust this build"
        )
    elif measured > exp.max_valuation_date:
        detail = "fresher than the pin: a new vintage - re-run the audit and re-pin expectations"
    return GateResult(
        "valuation_freshness",
        passed,
        exp.max_valuation_date.isoformat(),
        measured.isoformat(),
        detail,
    )


def check_funnel(measured: FunnelCounts, expected: FunnelCounts) -> list[GateResult]:
    """Exact equality per stage: any drift means the port no longer matches the audit."""
    stages = [
        "raw",
        "cleaned",
        "in_scope",
        "with_v_before",
        "observable",
        "with_v_after",
        "non_loan",
    ]
    return [
        GateResult(
            f"funnel_{stage}",
            getattr(measured, stage) == getattr(expected, stage),
            f"{getattr(expected, stage):,}",
            f"{getattr(measured, stage):,}",
        )
        for stage in stages
    ]


def check_transitions_floor(n_non_loan: int, exp: Expectations) -> GateResult:
    return GateResult(
        "transitions_non_loan_floor",
        n_non_loan >= exp.min_transitions_non_loan,
        f">= {exp.min_transitions_non_loan:,}",
        f"{n_non_loan:,}",
    )


def check_elo_coverage(coverage: float, exp: Expectations) -> GateResult:
    return GateResult(
        "elo_touch_coverage",
        coverage >= exp.min_elo_touch_coverage,
        f">= {exp.min_elo_touch_coverage:.2f}",
        f"{coverage:.4f}",
        "touch-weighted share of the transition universe with a mapped ClubElo club",
    )


def check_minutes_coverage(share: float, exp: Expectations) -> GateResult:
    return GateResult(
        "minutes_share_legacy_coverage",
        share >= exp.min_minutes_nonnull_legacy,
        f">= {exp.min_minutes_nonnull_legacy:.2f}",
        f"{share:.4f}",
        "non-null minutes_share_pre among legacy-league transitions since 2013",
    )


def check_manual_fixes(manual: pl.DataFrame, elo_names: set[str], club_ids: set[int]) -> GateResult:
    """Every manual row must resolve against the mirrors and clubs table."""
    problems: list[str] = []
    if manual["club_id"].n_unique() != manual.height:
        problems.append("duplicate club_id rows")
    if manual["elo_name"].n_unique() != manual.height:
        problems.append("duplicate elo_name rows")
    unknown_names = sorted(set(manual["elo_name"].to_list()) - elo_names)
    if unknown_names:
        problems.append(f"elo_name not in the mirrors: {unknown_names}")
    unknown_ids = sorted(set(manual["club_id"].to_list()) - club_ids)
    if unknown_ids:
        problems.append(f"club_id not in clubs.csv: {unknown_ids}")
    return GateResult(
        "manual_fixes_resolve",
        not problems,
        f"{manual.height} rows all resolve",
        "ok" if not problems else "; ".join(problems),
    )


def check_key_uniqueness(df: pl.DataFrame, subset: list[str], artifact: str) -> GateResult:
    dupes = df.height - df.select(subset).unique().height
    return GateResult(
        f"{artifact}_key_unique",
        dupes == 0,
        f"unique on ({', '.join(subset)})",
        "unique" if dupes == 0 else f"{dupes} duplicate keys",
    )


def check_non_empty(df: pl.DataFrame, artifact: str) -> GateResult:
    return GateResult(f"{artifact}_non_empty", df.height > 0, "> 0 rows", f"{df.height:,} rows")


def check_total_size(total_bytes: int, exp: Expectations) -> GateResult:
    return GateResult(
        "processed_total_size",
        total_bytes < exp.max_total_bytes,
        f"< {exp.max_total_bytes / 1024 / 1024:.0f} MB",
        f"{total_bytes / 1024 / 1024:.1f} MB",
    )
