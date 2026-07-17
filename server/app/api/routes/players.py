from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.clock import Clock, get_clock
from app.repositories.store import DataStore, get_store
from app.schemas.players import PlayerProfileResponse, PlayerSearchResult
from app.services.players import get_player_profile, search_players

router = APIRouter()


@router.get("/players/search")
def get_players_search(
    q: str,
    store: Annotated[DataStore, Depends(get_store)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> list[PlayerSearchResult]:
    return search_players(q, store, clock)


@router.get("/players/{player_id}")
def get_player(
    player_id: int,
    store: Annotated[DataStore, Depends(get_store)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> PlayerProfileResponse:
    return get_player_profile(player_id, store, clock)
