from pydantic import BaseModel


class DestinationClub(BaseModel):
    club_id: int
    name: str
    tercile: int
    elo_available: bool


class DestinationLeague(BaseModel):
    league_id: str
    name: str
    country: str | None
    tier: int
    clubs: list[DestinationClub]


class DestinationsResponse(BaseModel):
    season: int
    leagues: list[DestinationLeague]
