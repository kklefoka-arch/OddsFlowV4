"""OddsFlow V3 — Health check route."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Return service liveness status.

    Returns:
        JSON object with ``status`` and ``version`` fields.
    """
    return {"status": "ok", "version": "3.0.0"}
