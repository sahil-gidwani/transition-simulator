"""Simulation orchestrator: player + destination -> comps -> range -> narrative.

Everything shown traces back to the pool returned here: the prediction is a
weighted quantile OF these comps, and the narrative names them.
"""

from __future__ import annotations

from app.core.clock import Clock
from app.core.errors import ApiError
from app.repositories.store import DataStore
from app.schemas.simulations import (
    CompCard,
    PoolQualityOut,
    Prediction,
    SimDestination,
    SimPlayer,
    SimulationRequest,
    SimulationResponse,
)
from app.services.comps import build_query_context, find_comps
from app.services.constants import CLUB_INDISTINCT_MAX_MID_DRIFT, SHOWN_COMPS_DEFAULT
from app.services.destinations import league_label, resolve_destination
from app.services.narrative import build_narrative
from app.services.players import age_on
from app.services.valuation import direction_of, summarize_pool, weaker_confidence


def run_simulation(
    request: SimulationRequest, store: DataStore, clock: Clock
) -> SimulationResponse:
    player = store.players.get(request.player_id)
    if player is None:
        raise ApiError(404, "player_not_found", f"No player with id {request.player_id}")
    league, club = resolve_destination(
        request.destination.league_id, request.destination.club_id, store
    )
    query = build_query_context(player, store, clock)  # 409 when no current value
    result = find_comps(
        query,
        league,
        club,
        store.transitions.comps_universe,
        store.build_info.season_min,
    )
    value_range, confidence = summarize_pool(
        result.pool, query.value_eur, result.quality.relaxation_level
    )
    club_indistinct = False
    if club is not None and value_range is not None:
        # Honesty check on the PAIR of searches: if withholding the club
        # barely moves the midpoint, the club choice is below what this
        # precedent can resolve - say so instead of presenting reordered
        # noise as club-level differentiation. Judged on midpoint drift
        # alone: pool identity is irrelevant, because above POOL_K
        # candidates the club terms reshuffle which comps make the cap even
        # when the answer is unmoved.
        league_only = find_comps(
            query,
            league,
            None,
            store.transitions.comps_universe,
            store.build_info.season_min,
        )
        league_range, league_confidence = summarize_pool(
            league_only.pool, query.value_eur, league_only.quality.relaxation_level
        )
        if league_range is not None:
            drift = abs(value_range.q50_multiplier / league_range.q50_multiplier - 1)
            club_indistinct = drift <= CLUB_INDISTINCT_MAX_MID_DRIFT
        if club_indistinct:
            # An indistinct club pick adds no information, so it must not
            # RAISE the stated confidence above the league-only tier.
            confidence = weaker_confidence(confidence, league_confidence)
    dest_label = club.club_name if club is not None else league_label(league)
    narrative = build_narrative(
        player,
        dest_label,
        value_range,
        confidence,
        result.pool,
        result.quality,
        clock.today(),
        club_indistinct=club_indistinct,
    )

    prediction = None
    if value_range is not None:
        prediction = Prediction(
            low_eur=value_range.q25_eur,
            mid_eur=value_range.q50_eur,
            high_eur=value_range.q75_eur,
            low_multiplier=value_range.q25_multiplier,
            mid_multiplier=value_range.q50_multiplier,
            high_multiplier=value_range.q75_multiplier,
            horizon_months=12,
        )
    return SimulationResponse(
        player=SimPlayer(
            player_id=player.player_id,
            name=player.name,
            position_group=player.position_group,
            sub_position=player.sub_position,
            age=age_on(player.date_of_birth, clock.today()),
            market_value_eur=query.value_eur,
            market_value_asof=player.market_value_asof,
        ),
        destination=SimDestination(
            league_id=league.league,
            league_name=league_label(league),
            country=league.country,
            tier=league.tier,
            club_id=club.club_id if club is not None else None,
            club_name=club.club_name if club is not None else None,
            club_tercile=club.tercile if club is not None else None,
        ),
        prediction=prediction,
        direction=direction_of(value_range.q50_multiplier) if value_range is not None else None,
        confidence=confidence,
        insufficient_precedent=value_range is None,
        comps=[
            CompCard(
                player_id=comp.player_id,
                player_name=comp.player_name,
                season=comp.season,
                transfer_date=comp.transfer_date,
                age_at_transfer=comp.age_at_transfer,
                from_club=comp.from_club_name,
                to_club=comp.to_club_name,
                from_league=comp.from_league,
                to_league=comp.to_league,
                v_before_eur=comp.v_before,
                v_after_eur=comp.v_after,
                multiplier=comp.multiplier,
                delta_pct=comp.delta_pct,
                similarity=comp.similarity,
                tags=comp.tags,
            )
            for comp in result.pool
        ],
        shown_comps=SHOWN_COMPS_DEFAULT,
        pool_quality=PoolQualityOut(
            pool_size=result.quality.pool_size,
            relaxation_level=result.quality.relaxation_level,
            relaxation_steps=result.quality.relaxation_steps,
            expanded_search=result.quality.expanded_search,
            club_selected=result.quality.club_selected,
            elo_pool_coverage=result.quality.elo_pool_coverage,
            dest_elo_available=result.quality.dest_elo_available,
            missing_age=result.quality.missing_age,
            missing_minutes=result.quality.missing_minutes,
            origin_tier_unknown=result.quality.origin_tier_unknown,
            club_indistinct=club_indistinct,
            club_standing_support=result.quality.club_standing_support,
        ),
        narrative=narrative,
    )
