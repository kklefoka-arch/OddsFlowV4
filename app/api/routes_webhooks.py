"""OddsFlow V4 — Sportmonks Push webhook receiver (Session 23d Bundle 3).

Push-mode resilience layer on top of the polling pipeline. When Sportmonks
publishes a fixture state change (``fixture.finished`` / ``fixture.updated``),
they POST to this endpoint. The handler verifies the HMAC signature, looks
up the fixture, then reuses the same ``_write_and_settle()`` primitive that
the polling path (fetch_results.py + cron) uses — both paths converge on
one settlement function, so behaviour is identical regardless of source.

Polling stays as the fallback. If the webhook listener is down, ngrok URL
rotates, or signatures drift, the cron fetch_results at 23:30 / 03:15 /
06:15 SAST still settles within 24h.

Security:
    HMAC-SHA256 over the raw request body with
    ``settings.SPORTMONKS_WEBHOOK_SECRET``. Empty secret keeps the receiver
    in disabled mode and returns 503.

Idempotency:
    ``_write_and_settle()`` uses
    ``UPDATE fixtures ... WHERE home_score IS NULL`` so re-deliveries no-op
    once the fixture is settled, and ``INSERT OR IGNORE`` on ``pick_results``
    blocks double-settle.

Heartbeat:
    Every accepted call writes a ``sportmonks_webhook`` row to
    ``system_health`` so ``/diagnostics/runbook`` flags it overdue if
    Sportmonks stops calling.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.routes_results import (
    ACTIVE_LEAGUES,
    _BASE as SM_BASE,
    _TOKEN as SM_TOKEN,
    _parse_scores,
    _write_and_settle,
)
from app.db.database import get_conn
from app.settings import settings

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _verify_signature(raw_body: bytes, signature: str | None) -> bool:
    """Constant-time HMAC-SHA256 verification."""
    secret = settings.SPORTMONKS_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    sig = signature.lower().strip()
    if sig.startswith("sha256="):
        sig = sig[len("sha256="):]
    return hmac.compare_digest(expected, sig)


def _log_health(conn: sqlite3.Connection, value: str) -> None:
    try:
        conn.execute(
            "INSERT INTO system_health (metric, value) VALUES (?, ?)",
            ("sportmonks_webhook", value),
        )
        conn.commit()
    except Exception:
        pass


def _sm_fetch_scores(sportmonks_id: int) -> dict | None:
    """Pull the latest fixture body from Sportmonks v3 — scores + stats."""
    params = {
        "api_token": SM_TOKEN,
        "include":   "scores;statistics;participants",
    }
    url = f"{SM_BASE}/fixtures/{sportmonks_id}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as r:
            return json.loads(r.read())
    except Exception:
        return None


@router.post("/sportmonks")
async def sportmonks_webhook(
    request: Request,
    x_sportmonks_signature: str | None = Header(default=None, alias="X-Sportmonks-Signature"),
) -> dict[str, Any]:
    """Sportmonks Push receiver. See module docstring for full semantics.

    Returns a small JSON ack. Never raises beyond 4xx so Sportmonks doesn't
    enter retry storms — all real errors land in ``system_health``.
    """
    raw = await request.body()

    if not settings.SPORTMONKS_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="webhook disabled")

    if not _verify_signature(raw, x_sportmonks_signature):
        raise HTTPException(status_code=401, detail="bad signature")

    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    event = payload.get("event") or payload.get("type") or "unknown"
    data = payload.get("data") or {}
    fixture_sm_id = (
        data.get("fixture_id")
        or data.get("id")
        or (data.get("fixture") or {}).get("id")
    )
    league_id = data.get("league_id") or (data.get("league") or {}).get("id")

    now_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn(settings.sqlite_path)
    try:
        if not fixture_sm_id:
            _log_health(conn, f"error: missing fixture_id event={event} ts={now_ts}")
            return {"status": "ignored", "reason": "missing fixture_id"}

        if league_id is not None and league_id not in ACTIVE_LEAGUES:
            _log_health(conn, f"ok: skipped event={event} league_id={league_id} (not active) ts={now_ts}")
            return {"status": "ignored", "reason": "league not active"}

        row = conn.execute(
            "SELECT id FROM fixtures WHERE sportmonks_id = ?",
            (fixture_sm_id,),
        ).fetchone()
        if not row:
            _log_health(conn, f"ok: skipped event={event} sm_id={fixture_sm_id} (not in DB) ts={now_ts}")
            return {"status": "ignored", "reason": "fixture not in DB"}
        fixture_db_id = row["id"]

        scores_payload = data.get("scores")
        if not scores_payload:
            fresh = _sm_fetch_scores(fixture_sm_id) or {}
            scores_payload = (fresh.get("data") or {}).get("scores")
        home_score, away_score = _parse_scores(scores_payload or [])

        if home_score is None or away_score is None:
            _log_health(conn, f"ok: deferred event={event} sm_id={fixture_sm_id} (no scores yet) ts={now_ts}")
            return {"status": "deferred", "reason": "scores not yet available"}

        written, settled = _write_and_settle(
            conn, fixture_db_id, home_score, away_score, now_ts
        )
        conn.commit()
        msg = (
            f"ok: event={event} sm_id={fixture_sm_id} rows_written={written} "
            f"picks_settled={settled} ts={now_ts}"
        )
        _log_health(conn, msg)
        return {
            "status":        "ok",
            "event":         event,
            "fixture_id":    fixture_db_id,
            "rows_written":  written,
            "picks_settled": settled,
        }
    except HTTPException:
        raise
    except Exception as exc:
        try:
            _log_health(conn, f"error: event={event} {exc} ts={now_ts}")
        except Exception:
            pass
        # 200 so Sportmonks doesn't retry-storm us; runbook surfaces it.
        return {"status": "error", "detail": str(exc)}
    finally:
        try:
            conn.close()
        except Exception:
            pass
