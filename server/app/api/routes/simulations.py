from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.clock import Clock, get_clock
from app.repositories.store import DataStore, get_store
from app.schemas.simulations import SimulationRequest, SimulationResponse
from app.services.simulation import run_simulation

router = APIRouter()


@router.post("/simulations")
def post_simulation(
    request: SimulationRequest,
    store: Annotated[DataStore, Depends(get_store)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> SimulationResponse:
    return run_simulation(request, store, clock)
