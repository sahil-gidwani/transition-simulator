"""Serving-side tunables in one place.

PROVENANCE: hand-set priors (2026-07). The Prompt 5 temporal backtest tunes
and overwrites the retrieval weights, pool size and confidence thresholds -
treat every number here as provisional until that provenance comment says
otherwise.
"""

from __future__ import annotations

# --- search -------------------------------------------------------------------

SEARCH_MIN_QUERY_CHARS = 2  # shorter normalized queries return no results
SEARCH_LIMIT = 20
