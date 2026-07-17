from typing import Annotated

from fastapi import APIRouter, Depends

from app.repositories.store import DataStore, get_store
from app.schemas.destinations import DestinationsResponse
from app.services.destinations import get_destinations

router = APIRouter()


@router.get("/destinations")
def get_destinations_route(
    store: Annotated[DataStore, Depends(get_store)],
) -> DestinationsResponse:
    return get_destinations(store)
