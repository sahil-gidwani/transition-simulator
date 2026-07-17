"""Build metadata from data/processed/meta.json - the API's view of provenance."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel


class BuildInfo(BaseModel):
    repo: str
    revision: str
    built_at: str
    max_valuation_date: date
    censor_horizon: date
    season_min: int
    profile_min_minutes: int
    comps_universe_size: int


def read_build_info(path: Path) -> BuildInfo:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BuildInfo(
        repo=payload["source"]["repo"],
        revision=payload["source"]["revision"],
        built_at=payload["built_at"],
        max_valuation_date=payload["valuation_freshness"]["max_valuation_date"],
        censor_horizon=payload["valuation_freshness"]["censor_horizon"],
        season_min=payload["constants"]["season_min"],
        profile_min_minutes=payload["constants"]["profile_min_minutes"],
        comps_universe_size=payload["funnel"]["transitions_non_loan_2012_plus"],
    )
