"""The backtest's one leakage rule: date-exact comp availability.

Every consumer - the runner, the baselines, the tuning precompute and the
skyline's fold construction - goes through this single function, so the
definition of "what was knowable at time t" cannot drift between them.
"""

from __future__ import annotations

from datetime import date

import polars as pl


def available_universe(universe: pl.DataFrame, as_of: date) -> pl.DataFrame:
    """Comps usable at query time t: outcome already observed, v_after_date <= t.

    Inclusive on equality (a valuation posted on t is public by t). The
    query's own row always drops: its v_after_date is >= t + 180 days by
    construction of the v_after window, so no transition can inform a
    prediction about itself.
    """
    return universe.filter(pl.col("v_after_date") <= as_of)
