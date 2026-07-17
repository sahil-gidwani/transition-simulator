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
