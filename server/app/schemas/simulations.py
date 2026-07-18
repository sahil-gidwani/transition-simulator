from datetime import date
from typing import Literal

from pydantic import BaseModel


class DestinationSpec(BaseModel):
    league_id: str
    club_id: int | None = None


class SimulationRequest(BaseModel):
    player_id: int
    destination: DestinationSpec


class SimPlayer(BaseModel):
    player_id: int
    name: str
    position_group: str
    sub_position: str | None
    age: int | None
    market_value_eur: int
    market_value_asof: date | None


class SimDestination(BaseModel):
    league_id: str
    league_name: str
    country: str | None
    tier: int | None
    club_id: int | None
    club_name: str | None
    club_tercile: int | None


class Prediction(BaseModel):
    low_eur: int
    mid_eur: int
    high_eur: int
    low_multiplier: float
    mid_multiplier: float
    high_multiplier: float
    horizon_months: Literal[12]


class CompCard(BaseModel):
    player_id: int
    player_name: str
    season: int
    transfer_date: date
    age_at_transfer: float | None
    from_club: str
    to_club: str
    from_league: str | None
    to_league: str
    v_before_eur: int
    v_after_eur: int
    multiplier: float
    delta_pct: float
    similarity: float
    tags: list[str]


class PoolQualityOut(BaseModel):
    pool_size: int
    relaxation_level: int
    relaxation_steps: list[str]
    expanded_search: bool
    club_selected: bool
    elo_pool_coverage: float
    dest_elo_available: bool
    missing_age: bool
    missing_minutes: bool
    origin_tier_unknown: bool


class SimulationResponse(BaseModel):
    player: SimPlayer
    destination: SimDestination
    prediction: Prediction | None
    confidence: Literal["high", "medium", "low", "insufficient"]
    insufficient_precedent: bool
    comps: list[CompCard]
    shown_comps: int
    pool_quality: PoolQualityOut
    narrative: str
