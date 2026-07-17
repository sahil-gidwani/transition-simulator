from typing import Literal

from pydantic import BaseModel

Direction = Literal["higher_better", "lower_better"]


class MetricPercentile(BaseModel):
    metric: str
    label: str
    value: float | None
    percentile: int | None
    direction: Direction
    peer_n: int


class PercentilesResponse(BaseModel):
    player_id: int
    has_stats: bool
    season: int | None
    league_id: str | None
    minutes: int | None
    games_played: int | None
    below_floor: bool
    metrics: list[MetricPercentile]
