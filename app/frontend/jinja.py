"""Shared Jinja2Templates instance with OddsFlow V3 custom filters."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/frontend/templates")


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------

def _promote_badge(value: str | None) -> str:
    """Render a promotion status string as a styled HTML badge."""
    if value in ("PROMOTE",):
        return '<span class="badge-fire">&#9650; FIRE</span>'
    if value in ("PROMOTE_TOLERANCE",):
        return '<span class="badge-tol">&#9650; TOL</span>'
    if value == "HOLD":
        return '<span class="badge-hold">HOLD</span>'
    if value == "MEASURING":
        return '<span class="badge-meas">MEAS</span>'
    return '<span class="badge-no">—</span>'


def _fmt_pct(value: float | None, decimals: int = 1) -> str:
    """Format a float as a percentage string, e.g. 72.3%"""
    if value is None:
        return "—"
    return f"{value:.{decimals}f}%"


templates.env.filters["promote_badge"] = _promote_badge
templates.env.filters["fmt_pct"] = _fmt_pct
