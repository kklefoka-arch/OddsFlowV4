"""OddsFlow V3 — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.database import init_db
from app.settings import settings
from app.api.routes_health import router as health_router
from app.api.routes_foundation import router as foundation_router
from app.api.routes_fixtures import router as fixtures_router
from app.api.routes_inspector import router as inspector_router
from app.api.routes_ingest import router as ingest_router

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("OddsFlow V3 starting")
    init_db(settings.sqlite_path)
    yield


app = FastAPI(
    title="OddsFlow V3",
    version="3.0.0",
    description="Football betting analytics operator portal.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(foundation_router)
app.include_router(fixtures_router)
app.include_router(inspector_router)
app.include_router(ingest_router)

_static_dir = Path("app/frontend/static")
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
