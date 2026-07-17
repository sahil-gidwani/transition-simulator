"""Profile percentile panel: latest season, display-oriented directions.

Pipeline percentiles are raw-direction for EVERY metric (higher raw value =
higher percentile, including cards and goals conceded). This service flips
the bad-is-high metrics so the served percentile always reads as
better-than-peers, and says which way each metric points.
"""

from __future__ import annotations

from app.core.errors import ApiError
from app.repositories.store import DataStore
from app.schemas.percentiles import Direction, MetricPercentile, PercentilesResponse

_OUTFIELD_METRICS: list[tuple[str, str, Direction]] = [
    ("goals_p90", "Goals / 90", "higher_better"),
    ("assists_p90", "Assists / 90", "higher_better"),
    ("ga_p90", "Goals + assists / 90", "higher_better"),
    ("cards_p90", "Cards / 90", "lower_better"),
]
_GK_METRICS: list[tuple[str, str, Direction]] = [
    ("conceded_p90", "Goals conceded / 90", "lower_better"),
    ("clean_sheet_rate", "Clean-sheet rate", "higher_better"),
]


def _display_percentile(raw_pct: float | None, direction: Direction) -> int | None:
    if raw_pct is None:
        return None
    pct = 1.0 - raw_pct if direction == "lower_better" else raw_pct
    return round(100 * pct)


def get_percentiles(player_id: int, store: DataStore) -> PercentilesResponse:
    if store.players.get(player_id) is None:
        raise ApiError(404, "player_not_found", f"No player with id {player_id}")
    row = store.profiles.latest_row(player_id)
    if row is None:
        return PercentilesResponse(
            player_id=player_id,
            has_stats=False,
            season=None,
            league_id=None,
            minutes=None,
            games_played=None,
            below_floor=False,
            metrics=[],
        )
    metric_spec = _GK_METRICS if row["position_group"] == "GK" else _OUTFIELD_METRICS
    metrics = [
        MetricPercentile(
            metric=column,
            label=label,
            value=float(row[column]) if row[column] is not None else None,
            percentile=_display_percentile(row[f"pct_{column}"], direction),
            direction=direction,
            peer_n=row["peer_n"],
        )
        for column, label, direction in metric_spec
    ]
    return PercentilesResponse(
        player_id=player_id,
        has_stats=True,
        season=row["season"],
        league_id=row["league"],
        minutes=row["minutes"],
        games_played=row["games_played"],
        below_floor=row["minutes"] < store.build_info.profile_min_minutes,
        metrics=metrics,
    )
