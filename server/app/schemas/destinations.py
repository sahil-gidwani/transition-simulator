from pydantic import BaseModel


class DestinationClub(BaseModel):
    club_id: int
    name: str
    tercile: int | None
    squad_value_eur: int
    # Within-league squad-value percentile, 1.0 = richest; the picker's
    # human wording ("top club", "mid-table budget") derives from this.
    club_value_pct: float | None
    elo_available: bool


class DestinationLeague(BaseModel):
    league_id: str
    name: str
    country: str | None
    tier: int | None
    # ln(median derived squad value) and the median itself - the context the
    # picker shows so "league strength" is a number, not a vibe.
    strength: float | None
    median_squad_value_eur: int | None
    clubs: list[DestinationClub]


class DestinationsResponse(BaseModel):
    season: int
    leagues: list[DestinationLeague]
