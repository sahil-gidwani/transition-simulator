"""Backtest season splits and held-out query selection.

Validation (tuning, thresholds, calibration) strictly precedes every test
season; test seasons are scored exactly once, after the freeze. Season 2025
is excluded from evaluation entirely: it is right-censored (only transfers
whose v_after happened to land early are observable, a selection bias), but
its rows still serve as comps wherever the availability rule admits them.
"""

from __future__ import annotations

import polars as pl

VALIDATION_SEASONS: tuple[int, ...] = (2020, 2021)
TEST_SEASONS: tuple[int, ...] = (2022, 2023, 2024)


def eval_rows(universe: pl.DataFrame, seasons: tuple[int, ...]) -> pl.DataFrame:
    """The held-out queries for a phase, in deterministic iteration order."""
    return universe.filter(pl.col("season").is_in(list(seasons))).sort(
        ["season", "transfer_date", "player_id"]
    )
