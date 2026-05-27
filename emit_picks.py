"""Emit picks by calling the local /picks endpoint and recording to system_health.

Run after fetch_upcoming.py so odds are fresh before emission.
Part of the daily pipeline: fetch_upcoming -> emit_picks -> fetch_results -> settle.
"""
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone

DB  = r"C:\OddsFlowV4\data\oddsflow_v4.db"
URL = "http://localhost:8083/picks?days=3"

now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

try:
    resp = urllib.request.urlopen(URL, timeout=30)
    data = json.loads(resp.read())
    count   = data.get("count", 0)
    emit    = data.get("emit_log", {})
    new_n   = emit.get("new", 0)
    skip_n  = emit.get("skip", 0)
    msg = f"ok: picks={count} new={new_n} skip={skip_n} ts={now_ts}"
    print(f"Picks emitted: {count}  (new={new_n}  skip={skip_n})")
except Exception as exc:
    msg = f"error: {exc} ts={now_ts}"
    print(f"ERROR calling /picks: {exc}")

conn = sqlite3.connect(DB)
conn.execute(
    "INSERT INTO system_health (metric, value) VALUES (?, ?)",
    ("emit_picks", msg),
)
conn.commit()
conn.close()
