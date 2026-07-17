from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.destinations import router as destinations_router
from app.api.routes.health import router as health_router
from app.api.routes.players import router as players_router
from app.core.clock import Clock, SystemClock
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.repositories.store import DataStore, load_store


def create_app(store: DataStore | None = None, clock: Clock | None = None) -> FastAPI:
    """App factory. Tests inject a store built from synthetic frames; in
    production the lifespan loads the processed artifacts once at startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.store is None:
            app.state.store = load_store(get_settings().data_dir)
        yield

    app = FastAPI(title="Precedent API", lifespan=lifespan)
    app.state.store = store
    app.state.clock = clock if clock is not None else SystemClock()
    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(players_router, prefix="/api")
    app.include_router(destinations_router, prefix="/api")
    return app


app = create_app()
