"""Player-facing read services: search and profile assembly."""

from __future__ import annotations

from datetime import date

from app.core.clock import Clock
from app.core.errors import ApiError
from app.core.text import normalize_search_text, slug_to_title
from app.repositories.store import DataStore
from app.schemas.players import PlayerProfileResponse, PlayerSearchResult, ValuePointOut
from app.services.constants import SEARCH_LIMIT, SEARCH_MIN_QUERY_CHARS


def age_on(date_of_birth: date | None, today: date) -> int | None:
    if date_of_birth is None:
        return None
    birthday_passed = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if birthday_passed else 1)


def search_players(query: str, store: DataStore, clock: Clock) -> list[PlayerSearchResult]:
    query_norm = normalize_search_text(query)
    if len(query_norm) < SEARCH_MIN_QUERY_CHARS:
        return []
    today = clock.today()
    results: list[PlayerSearchResult] = []
    for rec in store.players.search(query_norm, SEARCH_LIMIT):
        league = store.seasons.league_latest(rec.current_league)
        league_name = slug_to_title(league.league_name) if league and league.league_name else None
        results.append(
            PlayerSearchResult(
                player_id=rec.player_id,
                name=rec.name,
                age=age_on(rec.date_of_birth, today),
                position_group=rec.position_group,
                sub_position=rec.sub_position,
                club_name=rec.current_club_name,
                league_id=rec.current_league,
                league_name=league_name,
                market_value_eur=rec.market_value_eur,
                market_value_asof=rec.market_value_asof,
            )
        )
    return results


def get_player_profile(player_id: int, store: DataStore, clock: Clock) -> PlayerProfileResponse:
    rec = store.players.get(player_id)
    if rec is None:
        raise ApiError(404, "player_not_found", f"No player with id {player_id}")
    league = store.seasons.league_latest(rec.current_league)
    return PlayerProfileResponse(
        player_id=rec.player_id,
        name=rec.name,
        position_group=rec.position_group,
        sub_position=rec.sub_position,
        date_of_birth=rec.date_of_birth,
        age=age_on(rec.date_of_birth, clock.today()),
        foot=rec.foot,
        height_cm=rec.height_cm,
        club_id=rec.current_club_id,
        club_name=rec.current_club_name,
        league_id=rec.current_league,
        league_name=slug_to_title(league.league_name) if league and league.league_name else None,
        league_tier=league.tier if league else None,
        last_season=rec.last_season,
        market_value_eur=rec.market_value_eur,
        market_value_asof=rec.market_value_asof,
        value_history=[
            ValuePointOut(date=point.date, value_eur=point.value_eur)
            for point in store.players.value_history(player_id)
        ],
    )
