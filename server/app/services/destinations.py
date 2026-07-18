"""Destination universe (latest season) and destination resolution."""

from __future__ import annotations

from app.core.errors import ApiError
from app.core.text import slug_to_title
from app.repositories.seasons import ClubSeason, LeagueSeason
from app.repositories.store import DataStore
from app.schemas.destinations import DestinationClub, DestinationLeague, DestinationsResponse


def league_label(league: LeagueSeason) -> str:
    """Human label; falls back to the league code when the slug is missing."""
    return slug_to_title(league.league_name) if league.league_name else league.league


def get_destinations(store: DataStore) -> DestinationsResponse:
    leagues = [
        DestinationLeague(
            league_id=ls.league,
            name=league_label(ls),
            country=ls.country,
            tier=ls.tier,
            strength=ls.strength,
            median_squad_value_eur=ls.median_squad_value_eur,
            clubs=[
                DestinationClub(
                    club_id=club.club_id,
                    name=club.club_name,
                    tercile=club.tercile,
                    squad_value_eur=club.squad_value_eur,
                    club_value_pct=club.club_value_pct,
                    elo_available=club.elo_pct is not None,
                )
                for club in store.seasons.clubs_latest(ls.league)
            ],
        )
        for ls in store.seasons.leagues_latest()
    ]
    return DestinationsResponse(season=store.seasons.latest_season, leagues=leagues)


def resolve_destination(
    league_id: str, club_id: int | None, store: DataStore
) -> tuple[LeagueSeason, ClubSeason | None]:
    """The simulation target: a latest-season league, optionally one of its clubs."""
    league = store.seasons.league_latest(league_id)
    if league is None:
        raise ApiError(404, "destination_not_found", f"No destination league '{league_id}'")
    club = None
    if club_id is not None:
        club = store.seasons.club_latest(club_id)
        if club is None or club.league != league_id:
            raise ApiError(
                404,
                "destination_not_found",
                f"No club {club_id} in league '{league_id}' this season",
            )
    return league, club
