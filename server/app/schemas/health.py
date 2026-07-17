from datetime import date
from typing import Literal

from pydantic import BaseModel


class DataBuildInfo(BaseModel):
    repo: str
    revision: str
    built_at: str
    max_valuation_date: date
    censor_horizon: date
    comps_universe_size: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    data: DataBuildInfo
