"""OddsFlow V4 — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.database import init_db
from app.settings import settings
from app.api.routes_health import router as health_router
from app.api.routes_foundation import router as foundation_router
from app.api.routes_fixtures import router as fixtures_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_picks import router as picks_router
from app.api.routes_upcoming import router as upcoming_router
from app.api.routes_reports import router as reports_router
from app.api.routes_inspector import router as inspector_router
from app.api.routes_diagnostics import router as diagnostics_router
from app.api.routes_results import router as results_router
from app.api.routes_webhooks import router as webhooks_router

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "frontend" / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("OddsFlow V4 starting")
    init_db(settings.sqlite_path)
    yield


app = FastAPI(
    title="OddsFlow V4",
    version="4.0.0",
    description="Football betting analytics engine — operator portal.",
    lifespan=lifespan,
)

# ---- API routers ----
app.include_router(health_router)
app.include_router(picks_router)
app.include_router(upcoming_router)
app.include_router(foundation_router)
app.include_router(fixtures_router)
app.include_router(ingest_router)
app.include_router(reports_router)
app.include_router(inspector_router)
app.include_router(diagnostics_router)
app.include_router(results_router)
app.include_router(webhooks_router)


# ---- /healthz/deep (wired separately so the SPA health badge works) ----
@app.get("/healthz/deep", include_in_schema=False)
async def healthz_deep() -> dict:
    from app.api.routes_diagnostics import _healthz_deep_impl
    return _healthz_deep_impl()


# ---- SPA: serve engine_view.html at "/" and "/engine" ----
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/engine", response_class=HTMLResponse, include_in_schema=False)
async def spa(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse("engine_view.html", {"request": request})


# ---- Static files ----
_static_dir = Path(__file__).parent / "frontend" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
