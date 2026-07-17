from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


def _server_version() -> str:
    try:
        return version("precedent-server")
    except PackageNotFoundError:
        return "0.0.0"


@router.get("/health")
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=_server_version())
