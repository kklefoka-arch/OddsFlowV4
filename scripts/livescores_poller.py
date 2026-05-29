"""
OddsFlow V4 — Livescores poller (Session 23d follow-up, 2026-05-29)
====================================================================
Polls the local ``/api/livescores`` endpoint which proxies Sportmonks'
``livescores/inplay`` feed, filters by ``ACTIVE_LEAGUES``, writes scores
for any fixture whose ``state.short_name`` is FT/AET/FT_PEN/FINISHED/
AWARDED, and settles pending picks for that fixture via the existing
``_write_and_settle()`` helper.

Effective settlement latency = the scheduler interval (~5 min) instead
of the 8-hour worst case under the polling cron alone.

This replaces the "Sportmonks webhook" recommendation. Sportmonks v3
does not document a public webhook/push registration flow — their
official real-time pattern is polling the livescores endpoint. This
script implements that pattern; the existing ``/api/webhooks/sportmonks``
scaffold stays in place (returns 503 when SECRET unset) for any future
push support without further code changes.

Scheduled via ``OddsFlow_LivescoresPoller`` in ``setup_scheduler.ps1``
(every 5 minutes — adjust there for tighter / looser cadence).

Heartbeat: writes a ``livescores_poller`` row to ``system_health`` so
``/diagnostics/runbook`` surfaces a missed window within its 30-min
threshold (see ``app/settings.RUNBOOK_THRESHOLDS``).
"""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from datetime import datetime, timezone

DB  = r"C:\OddsFlowV4\data\oddsflow_v4.db"
URL = "http://localhost:8083/api/livescores"


def main() -> None:
    now_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with urllib.request.urlopen(URL, timeout=20) as r:
            body = json.loads(r.read())
        count   = body.get("count", 0)
        written = body.get("auto_written", 0)
        settled = body.get("auto_settled", 0)
        err     = body.get("error")
        if err:
            msg = f"error: livescores upstream {err} ts={now_ts}"
        else:
            msg = (
                f"ok: livescores={count} auto_written={written} "
                f"auto_settled={settled} ts={now_ts}"
            )
        print(msg)
    except Exception as exc:
        msg = f"error: {exc} ts={now_ts}"
        print(f"ERROR calling {URL}: {exc}")

    try:
        conn = sqlite3.connect(DB)
        conn.execute(
            "INSERT INTO system_health (metric, value) VALUES (?, ?)",
            ("livescores_poller", msg),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
