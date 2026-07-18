"""Historical query construction: one transitions row -> the serving inputs.

Rebuilds exactly what the engine would have seen at the transfer date:
value = v_before, age = age_at_transfer, origin context from the from_*
columns, latest_season = the query's own season (so the recency term is
measured from t, not from today).

One deliberate deviation from live serving: destination context is built
as-of the QUERY'S season (league_at/club_at), where serving uses the latest
season. The backtest is a faithful historical simulation, so both sides of
the strength comparison are as-of dates <= t.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.repositories.players import PlayerRecord
from app.repositories.seasons import ClubSeason, LeagueSeason, SeasonsRepo
from app.services.comps import QueryContext


@dataclass(frozen=True)
class EvalQuery:
    """One held-out transition, expressed as the serving engine's inputs."""

    query: QueryContext
    dest_league: LeagueSeason
    dest_club: ClubSeason | None
    player_id: int
    transfer_date: date
    season: int
    v_before: int
    v_after: int
    actual_multiplier: float
    age_at_transfer: float | None
    position_group: str
    from_tier: int | None
    to_tier: int
    minutes_known: bool


@dataclass(frozen=True)
class SkippedQuery:
    """A transition the backtest cannot simulate; counted, never hidden."""

    player_id: int
    transfer_date: date
    season: int
    # "null_to_league" | "dest_league_missing" | "dest_league_stats_invalid"
    # | "nonpositive_v_before"
    reason: str


def _skip(row: dict[str, Any], reason: str) -> SkippedQuery:
    return SkippedQuery(
        player_id=row["player_id"],
        transfer_date=row["transfer_date"],
        season=row["season"],
        reason=reason,
    )


def build_eval_query(row: dict[str, Any], seasons: SeasonsRepo) -> EvalQuery | SkippedQuery:
    if row["v_before"] is None or row["v_before"] <= 0:
        return _skip(row, "nonpositive_v_before")
    if row["to_league"] is None:
        return _skip(row, "null_to_league")
    dest_league = seasons.league_at(row["to_league"], row["season"])
    if dest_league is None:
        return _skip(row, "dest_league_missing")
    if dest_league.strength is None or dest_league.tier is None:
        # Below the minimum-club floor: no honest strength stats to query.
        return _skip(row, "dest_league_stats_invalid")
    dest_club = seasons.club_at(row["to_club_id"], row["season"])

    origin_strength: float | None = None
    if row["from_league"] is not None:
        origin_league = seasons.league_at(row["from_league"], row["season"])
        if origin_league is not None:
            origin_strength = origin_league.strength

    # Only position_group/sub_position are consumed downstream, but the
    # record is synthesized in full from at-transfer values so nothing
    # post-t can leak through it.
    player = PlayerRecord(
        player_id=row["player_id"],
        name=row["player_name"],
        position_group=row["position_group"],
        sub_position=row["sub_position"],
        date_of_birth=None,
        foot=None,
        height_cm=None,
        current_club_id=row["from_club_id"],
        current_club_name=row["from_club_name"],
        current_league=row["from_league"] or "",
        market_value_eur=row["v_before"],
        market_value_asof=row["v_before_date"],
        last_season=row["season"],
    )
    query = QueryContext(
        player=player,
        value_eur=row["v_before"],
        age=row["age_at_transfer"],
        origin_tier=row["from_tier"],
        origin_strength=origin_strength,
        origin_club_value_pct=row["from_club_value_pct"],
        minutes_share=row["minutes_share_pre"],
        latest_season=row["season"],
    )
    return EvalQuery(
        query=query,
        dest_league=dest_league,
        dest_club=dest_club,
        player_id=row["player_id"],
        transfer_date=row["transfer_date"],
        season=row["season"],
        v_before=row["v_before"],
        v_after=row["v_after"],
        actual_multiplier=row["multiplier"],
        age_at_transfer=row["age_at_transfer"],
        position_group=row["position_group"],
        from_tier=row["from_tier"],
        to_tier=row["to_tier"],
        minutes_known=row["minutes_share_pre"] is not None,
    )
