"""
OddsFlow V4 — Orphan pick reconciler (Session 23d Bundle 4)
============================================================
Picks become "orphaned" when they cannot be settled through the normal
results+settle pipeline. Two causes today:

  1. The fixture's league_id is no longer in ACTIVE_LEAGUES (e.g. USL2
     was dropped Session 23). fetch_results never queries those leagues
     again, so the fixture sits without scores forever.
  2. The fixture's kickoff was more than 48 hours ago, the fixture has
     no scores yet, and the league IS in ACTIVE_LEAGUES — Sportmonks
     simply never returned the result. Practical outcome equivalent to #1.

Both cases are written as a synthetic ``pick_results`` row with
``outcome='ORPHAN'`` and ``notes='<reason>'``. The pick drops out of the
"pending" count in the operator dashboard and the runbook stays clean,
without faking a win/loss/void.

Run nightly via the Windows scheduler (slot added by setup_scheduler.ps1
under task name ``OddsFlow_ReconcileOrphans``).

Heartbeat: writes a ``reconcile_orphans`` row to ``system_health`` with
``value`` summarising counts, picked up by ``/diagnostics/runbook``.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "oddsflow_v4.db"
# Match the active league set used by fetch_results / routes_results.
# Keep this in sync; if it drifts, the reconciler will mark fewer picks
# than expected — visible in the runbook value.
ACTIVE_LEAGUES = {
    # T1
    573, 444, 345, 292, 360, 779, 648, 3537, 1034,
    # T2
    393, 405, 579, 585, 588, 681, 678, 696, 1689, 295, 286, 289, 791, 3550, 989,
    # T3 (USL League Two 797 dropped 2026-05-29)
    1642, 351, 1607, 2545, 1098,
}
ORPHAN_AGE_HOURS = 48  # fixture older than this with no score + no settlement


def _write_health(conn: sqlite3.Connection, value: str) -> None:
    """Best-effort heartbeat; never raise out of the reconciler."""
    try:
        conn.execute(
            "INSERT INTO system_health (metric, value) VALUES (?, ?)",
            ("reconcile_orphans", value),
        )
        conn.commit()
    except Exception:
        pass


def _mark_orphans(conn: sqlite3.Connection, reason: str, where_sql: str, params: list) -> int:
    """Insert synthetic pick_results rows with outcome='ORPHAN'.

    Idempotent — INSERT OR IGNORE on pick_uuid will skip picks already
    settled (real WIN/LOSS/VOID) and also already-marked orphans.
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        f"""
        SELECT em.pick_uuid
        FROM emit_log em
        JOIN fixtures f         ON f.id = em.fixture_id
        LEFT JOIN pick_results pr ON pr.pick_uuid = em.pick_uuid
        WHERE pr.pick_uuid IS NULL
          AND {where_sql}
        """,
        params,
    ).fetchall()
    if not rows:
        return 0
    inserted = 0
    for r in rows:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO pick_results
              (pick_uuid, settled_at, outcome, actual_value, notes)
            VALUES (?, ?, 'ORPHAN', NULL, ?)
            """,
            (r["pick_uuid"], now, reason),
        )
        if cur.rowcount > 0:
            inserted += 1
    return inserted


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Reason A — fixture's league_id no longer in ACTIVE_LEAGUES.
        league_placeholders = ",".join("?" * len(ACTIVE_LEAGUES))
        league_count = _mark_orphans(
            conn,
            reason="league_dropped",
            where_sql=f"f.league_id NOT IN ({league_placeholders})",
            params=list(ACTIVE_LEAGUES),
        )
        # Reason B — kickoff > 48h ago, league still active, but no scores.
        stale_count = _mark_orphans(
            conn,
            reason="stale_no_result",
            where_sql=(
                f"f.league_id IN ({league_placeholders}) "
                f"AND f.home_score IS NULL "
                f"AND f.date < datetime('now', '-{ORPHAN_AGE_HOURS} hours')"
            ),
            params=list(ACTIVE_LEAGUES),
        )
        total = league_count + stale_count
        _write_health(
            conn,
            f"ok: league_dropped={league_count} stale_no_result={stale_count} total={total}",
        )
        print(
            f"reconcile_orphans: league_dropped={league_count} "
            f"stale_no_result={stale_count} total={total}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
