from datetime import date

from pydantic import BaseModel


class PlayerSearchResult(BaseModel):
    player_id: int
    name: str
    age: int | None
    position_group: str
    sub_position: str | None
    club_name: str
    league_id: str
    league_name: str | None
    market_value_eur: int | None
    market_value_asof: date | None
    # Fraction vs the latest valuation 12+ months ago (0.2 = +20%); null when
    # no baseline that old exists.
    value_delta_12m: float | None


class ValuePointOut(BaseModel):
    date: date
    value_eur: int


class TransferEventOut(BaseModel):
    date: date
    from_club: str
    to_club: str


class PlayerProfileResponse(BaseModel):
    player_id: int
    name: str
    position_group: str
    sub_position: str | None
    date_of_birth: date | None
    age: int | None
    foot: str | None
    height_cm: int | None
    club_id: int
    club_name: str
    league_id: str
    league_name: str | None
    league_tier: int | None
    last_season: int
    market_value_eur: int | None
    market_value_asof: date | None
    value_history: list[ValuePointOut]
    # The player's own qualifying (non-loan) moves — the chart's annotations.
    transfers: list[TransferEventOut]
