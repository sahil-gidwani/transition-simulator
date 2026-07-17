from datetime import date

import polars as pl

from pipeline.config import PINNED_EXPECTATIONS, FunnelCounts
from pipeline.gates import (
    check_funnel,
    check_manifest_pin,
    check_manual_fixes,
    check_total_size,
    check_valuation_freshness,
    render_gate_table,
)
from pipeline.io import TablesSource

_REPO = "mirror/repo"
_REV = "abc123"


def test_manifest_pin_accepts_only_the_pinned_revision() -> None:
    good = TablesSource(source="huggingface", repo=_REPO, revision=_REV)
    assert check_manifest_pin(good, _REPO, _REV).passed
    assert not check_manifest_pin(None, _REPO, _REV).passed
    wrong_rev = TablesSource(source="huggingface", repo=_REPO, revision="ffff")
    assert not check_manifest_pin(wrong_rev, _REPO, _REV).passed
    kaggle = TablesSource(source="kaggle", repo=None, revision=None)
    assert not check_manifest_pin(kaggle, _REPO, _REV).passed


def test_freshness_gate_names_the_frozen_vintage_failure() -> None:
    # The defective Kaggle distribution shipped valuations frozen at 2026-02-27.
    frozen = check_valuation_freshness(date(2026, 2, 27), PINNED_EXPECTATIONS)
    assert not frozen.passed
    assert "frozen" in frozen.detail
    fresh = check_valuation_freshness(date(2026, 6, 12), PINNED_EXPECTATIONS)
    assert fresh.passed


def test_funnel_gate_flags_exactly_the_drifted_stage() -> None:
    expected = FunnelCounts(100, 99, 50, 45, 40, 38, 20)
    measured = FunnelCounts(100, 99, 50, 45, 40, 38, 19)
    results = check_funnel(measured, expected)
    failed = [g.name for g in results if not g.passed]
    assert failed == ["funnel_non_loan"]


def _manual(rows: list[tuple[str, int]]) -> pl.DataFrame:
    return pl.DataFrame(
        [(name, cid, "tm", "note") for name, cid in rows],
        schema={
            "elo_name": pl.String,
            "club_id": pl.Int64,
            "tm_name": pl.String,
            "note": pl.String,
        },
        orient="row",
    )


def test_manual_fixes_gate_catches_typos_and_duplicates() -> None:
    names = {"Lille", "Betis"}
    ids = {1, 2}
    assert check_manual_fixes(_manual([("Lille", 1)]), names, ids).passed
    assert not check_manual_fixes(_manual([("Lile", 1)]), names, ids).passed
    assert not check_manual_fixes(_manual([("Lille", 99)]), names, ids).passed
    assert not check_manual_fixes(_manual([("Lille", 1), ("Lille", 2)]), names, ids).passed
    assert not check_manual_fixes(_manual([("Lille", 1), ("Betis", 1)]), names, ids).passed


def test_total_size_gate_is_a_strict_ceiling() -> None:
    limit = PINNED_EXPECTATIONS.max_total_bytes
    assert check_total_size(limit - 1, PINNED_EXPECTATIONS).passed
    assert not check_total_size(limit, PINNED_EXPECTATIONS).passed


def test_gate_table_renders_pass_and_fail() -> None:
    gates = check_funnel(FunnelCounts(1, 1, 1, 1, 1, 1, 1), FunnelCounts(1, 1, 1, 1, 1, 1, 2))
    table = render_gate_table(gates)
    assert "| funnel_raw | PASS |" in table
    assert "| funnel_non_loan | FAIL |" in table
