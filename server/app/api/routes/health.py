from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

from fastapi import APIRouter, Depends

from app.repositories.store import DataStore, get_store
from app.schemas.health import DataBuildInfo, HealthResponse

router = APIRouter()


def _server_version() -> str:
    try:
        return version("precedent-server")
    except PackageNotFoundError:
        return "0.0.0"


@router.get("/health")
def get_health(store: Annotated[DataStore, Depends(get_store)]) -> HealthResponse:
    info = store.build_info
    return HealthResponse(
        status="ok",
        version=_server_version(),
        data=DataBuildInfo(
            repo=info.repo,
            revision=info.revision,
            built_at=info.built_at,
            max_valuation_date=info.max_valuation_date,
            censor_horizon=info.censor_horizon,
            comps_universe_size=info.comps_universe_size,
        ),
    )
