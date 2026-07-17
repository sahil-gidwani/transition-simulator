from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.clock import Clock, get_clock
from app.repositories.store import DataStore, get_store
from app.schemas.players import PlayerSearchResult
from app.services.players import search_players

router = APIRouter()


@router.get("/players/search")
def get_players_search(
    q: str,
    store: Annotated[DataStore, Depends(get_store)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> list[PlayerSearchResult]:
    return search_players(q, store, clock)
