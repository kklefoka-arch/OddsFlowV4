"""
OddsFlow V4 — Weekly DB maintenance (Session 23d Bundle 6)
===========================================================
Keeps the SQLite DB compact and query-planner stats fresh over long-haul
runtime. Run weekly via the Windows scheduler.

Actions:
  - ``PRAGMA optimize``   — incremental index maintenance.
  - ``ANALYZE``           — refresh statistics so the query planner stays
                            accurate as table sizes grow.
  - ``VACUUM``            — only when the DB has been written to since
                            the last maintenance run (uses ``PRAGMA page_count``
                            growth as a cheap heuristic). Rebuilds the file
                            to reclaim space.
  - Pre-VACUUM backup     — copies the DB to ``data/oddsflow_v4.db.bak.YYYY-MM-DD``
                            so VACUUM can be rolled back if anything goes wrong.

Heartbeat: writes ``db_maintenance`` row to ``system_health`` for the runbook.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "oddsflow_v4.db"
VACUUM_MIN_PAGE_GROWTH = 500  # ~2 MB at default page_size — avoid VACUUM on quiet weeks


def _write_health(conn: sqlite3.Connection, value: str) -> None:
    try:
        conn.execute(
            "INSERT INTO system_health (metric, value) VALUES (?, ?)",
            ("db_maintenance", value),
        )
        conn.commit()
    except Exception:
        pass


def main() -> None:
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}")
        return
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    size_before = DB_PATH.stat().st_size

    # PRAGMA optimize + ANALYZE run inside a normal connection.
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA optimize")
        conn.execute("ANALYZE")
        conn.commit()
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    finally:
        conn.close()

    # Decide whether to VACUUM. Compare against the last reported page_count
    # from system_health for cheap delta detection.
    do_vacuum = False
    conn = sqlite3.connect(DB_PATH)
    try:
        last_row = conn.execute(
            """SELECT value FROM system_health
               WHERE metric = 'db_maintenance' AND value LIKE 'ok:%'
               ORDER BY recorded_at DESC LIMIT 1"""
        ).fetchone()
    finally:
        conn.close()
    last_pages = 0
    if last_row:
        try:
            for part in (last_row[0] or "").split():
                if part.startswith("page_count="):
                    last_pages = int(part.split("=", 1)[1])
                    break
        except Exception:
            last_pages = 0
    if page_count - last_pages >= VACUUM_MIN_PAGE_GROWTH:
        do_vacuum = True

    vacuumed = False
    if do_vacuum:
        # Backup before VACUUM. shutil.copy2 preserves mtime; if VACUUM fails,
        # operator can restore from the dated backup.
        backup = DB_PATH.with_name(f"oddsflow_v4.db.bak.{today}")
        try:
            if not backup.exists():
                shutil.copy2(DB_PATH, backup)
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute("VACUUM")
                conn.commit()
                vacuumed = True
            finally:
                conn.close()
        except Exception as exc:
            print(f"VACUUM failed: {exc}")

    size_after = DB_PATH.stat().st_size

    msg = (
        f"ok: page_count={page_count} vacuumed={vacuumed} "
        f"size_before_kb={size_before // 1024} size_after_kb={size_after // 1024}"
    )
    # Write the heartbeat through a fresh connection (post-VACUUM if applicable).
    conn = sqlite3.connect(DB_PATH)
    try:
        _write_health(conn, msg)
    finally:
        conn.close()
    print(msg)


if __name__ == "__main__":
    main()
