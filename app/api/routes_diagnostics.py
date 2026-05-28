"""OddsFlow V4 — Diagnostic endpoints (today_summary, db_state, odds_coverage, heartbeat, drift_report)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.db.database import get_conn
from app.settings import settings

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------
# V3.1 (2026-05-28): the daily pipeline is split across 12 Task Scheduler
# jobs that each write their own metric. "cron freshness" = the most recent
# row across any of these. "last clean run" = the most recent terminal step
# (settle), since settle runs at the end of every daily window. The legacy
# `cron_heartbeat` row from run_daily.ps1 is included for backwards-compat.
_PIPELINE_METRICS: tuple[str, ...] = (
    "cron_heartbeat",
    "fetch_upcoming",
    "emit_picks",
    "refresh_odds",
    "fetch_results",
    "refresh_stats",
    "settle",
)
_TERMINAL_METRIC = "settle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_count(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return None


def _latest_pipeline_row(conn: sqlite3.Connection,
                          metrics: tuple[str, ...] = _PIPELINE_METRICS):
    """Most recent system_health row across any pipeline metric."""
    placeholders = ",".join("?" * len(metrics))
    return conn.execute(
        f"""SELECT metric, recorded_at, value FROM system_health
            WHERE metric IN ({placeholders})
            ORDER BY recorded_at DESC LIMIT 1""",
        metrics,
    ).fetchone()


def _latest_terminal_row(conn: sqlite3.Connection):
    """Most recent terminal-step (settle) row, plus legacy cron_heartbeat with step=complete."""
    return conn.execute(
        """SELECT metric, recorded_at, value FROM system_health
           WHERE metric = ?
              OR (metric = 'cron_heartbeat' AND value LIKE '%step=complete%')
           ORDER BY recorded_at DESC LIMIT 1""",
        (_TERMINAL_METRIC,),
    ).fetchone()


# ---------------------------------------------------------------------------
# GET /diagnostics/today_summary
# ---------------------------------------------------------------------------

@router.get("/today_summary")
def today_summary() -> dict[str, Any]:
    """Operator dashboard. Engine activity + drift summary for the Today tab."""
    now = datetime.now(tz=timezone.utc)
    today_sql = now.strftime("%Y-%m-%d")
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn(settings.sqlite_path)
    try:
        # Fixtures kicking off today (date stores full datetime, use substr match)
        kickoff_today = conn.execute(
            "SELECT COUNT(*) FROM fixtures WHERE substr(date,1,10) = ?", (today_sql,)
        ).fetchone()[0]

        fetched_24h = conn.execute(
            "SELECT COUNT(*) FROM fixtures WHERE created_at >= ? OR updated_at >= ?",
            (cutoff_24h, cutoff_24h),
        ).fetchone()[0]

        # Picks emitted today
        emitted_today = conn.execute(
            "SELECT COUNT(*) FROM emit_log WHERE emitted_at >= ?", (today_sql,)
        ).fetchone()[0]

        # By market today
        by_market_rows = conn.execute(
            "SELECT market, COUNT(*) AS n FROM emit_log WHERE emitted_at >= ? GROUP BY market",
            (today_sql,),
        ).fetchall()
        by_market_today = {r["market"]: r["n"] for r in by_market_rows}

        # DB state
        fixtures_total = _safe_count(conn, "fixtures") or 0
        fixtures_settled = conn.execute(
            "SELECT COUNT(*) FROM fixtures WHERE home_score IS NOT NULL"
        ).fetchone()[0]
        emit_total = _safe_count(conn, "emit_log") or 0
        emit_settled = conn.execute(
            """SELECT COUNT(*) FROM emit_log em
               JOIN fixtures f ON f.id = em.fixture_id
               WHERE f.home_score IS NOT NULL"""
        ).fetchone()[0]

        # Cron heartbeat — V3.1 multi-metric.
        # Freshness reflects the LATEST pipeline metric (any of fetch_upcoming,
        # emit_picks, refresh_odds, fetch_results, refresh_stats, settle, or
        # legacy cron_heartbeat). last_clean_run reflects the most recent
        # terminal step (settle) — the end of any daily window.
        cron: dict[str, Any] = {
            "status": "never_fired",
            "age_hours": None,
            "last_metric": None,
            "last_clean_run": None,
        }
        try:
            lh = _latest_pipeline_row(conn)
            if lh and lh["recorded_at"]:
                try:
                    ts = datetime.fromisoformat(lh["recorded_at"].replace(" ", "T"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age_h = round((now - ts).total_seconds() / 3600, 1)
                    cron["status"] = "fresh" if age_h <= 26 else ("warning" if age_h <= 48 else "stale")
                    cron["age_hours"] = age_h
                    cron["last_metric"] = lh["metric"]
                except Exception:
                    pass
            lc = _latest_terminal_row(conn)
            if lc and lc["recorded_at"]:
                try:
                    ts = datetime.fromisoformat(lc["recorded_at"].replace(" ", "T"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age_h = round((now - ts).total_seconds() / 3600, 1)
                    cron["last_clean_run"] = {
                        "recorded_at": lc["recorded_at"],
                        "age_hours": age_h,
                        "metric": lc["metric"],
                    }
                except Exception:
                    pass
        except Exception:
            pass

        # Drift summary
        drift: dict[str, Any] = {}
        try:
            from app.api.routes_inspector import compute_drift_rows
            drift_rows = compute_drift_rows(conn, recent_days=30)
            drift = {
                "stable":   sum(1 for r in drift_rows if r["flag"] == "stable"),
                "watch":    sum(1 for r in drift_rows if r["flag"] == "watch"),
                "drifting": sum(1 for r in drift_rows if r["flag"] == "drifting"),
                "no_data":  sum(1 for r in drift_rows if r["flag"] == "no_data"),
            }
        except Exception as e:
            drift = {"error": str(e)}

        # Emit performance summary (7d and 30d)
        from app.api.routes_picks import settle_pick
        cutoff_180 = (now - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
        emit_rows = conn.execute(
            """SELECT em.emitted_at, em.fixture_id, em.market, em.pick,
                      f.home_score, f.away_score, f.home_odd, f.away_odd,
                      fs.total_corners
               FROM emit_log em
               JOIN fixtures f ON f.id = em.fixture_id
               LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
               WHERE em.emitted_at >= ?""",
            (cutoff_180,),
        ).fetchall()

        legs = []
        for r in emit_rows:
            try:
                at = datetime.fromisoformat((r["emitted_at"] or "").replace(" ", "T"))
                if at.tzinfo is None:
                    at = at.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            # V3.1 (2026-05-28): pass pick + total_corners so corners_nl settles.
            outcome = settle_pick(r["market"], r["home_score"], r["away_score"],
                                   r["home_odd"], r["away_odd"],
                                   r["pick"] or "", total_corners=r["total_corners"])
            legs.append((at, r["fixture_id"], r["market"], outcome))

        def _window_stats(days_back: int) -> dict:
            cutoff = now - timedelta(days=days_back)
            in_w = [l for l in legs if l[0] >= cutoff]
            events: dict[tuple[int, str], list[float]] = {}
            for (_, fid, mkt, outcome) in in_w:
                if outcome is None:
                    continue
                events.setdefault((fid, mkt), []).append(outcome)
            settled = len(events)
            wins_ev = sum(1 for outs in events.values() if any(o == 1.0 for o in outs))
            voids_ev = sum(1 for outs in events.values()
                           if all(o != 1.0 for o in outs) and any(o == 0.5 for o in outs))
            losses_ev = settled - wins_ev - voids_ev
            # V3.1 (2026-05-28): V3 non-loss hit rate — voids count as wins.
            hit_ev = round((wins_ev + voids_ev) / settled * 100, 1) if settled > 0 else None
            n_legs = len([l for l in in_w if l[3] is not None])
            return {
                "legs":   {"total": len(in_w), "settled": n_legs},
                "events": {"settled": settled, "wins": wins_ev,
                           "voids": voids_ev, "losses": losses_ev, "hit_rate": hit_ev},
            }

    finally:
        conn.close()

    return {
        "as_of": now.isoformat(),
        "cron":  cron,
        "chain": {"verified": None},
        "drift": drift,
        "fixtures": {
            "kickoff_today":    kickoff_today,
            "fetched_last_24h": fetched_24h,
        },
        "picks": {
            "emitted_today":  emitted_today,
            "by_market_today": by_market_today,
        },
        "locks": {
            "pending":        0,
            "settled_today":  0,
            "pnl_today_zar":  0.0,
        },
        "engine": {
            "window_7d":  _window_stats(7),
            "window_30d": _window_stats(30),
        },
        "db": {
            "fixtures_total":   fixtures_total,
            "fixtures_settled": fixtures_settled,
            "emit_total":       emit_total,
            "emit_settled":     emit_settled,
            "locked_by_state":  {},
        },
    }


# ---------------------------------------------------------------------------
# GET /diagnostics/db_state
# ---------------------------------------------------------------------------

@router.get("/db_state")
def db_state() -> dict[str, Any]:
    """Row counts across core tables."""
    conn = get_conn(settings.sqlite_path)
    try:
        tables = ["fixtures", "fixture_stats", "teams", "leagues",
                  "emit_log", "pick_results", "h2h_meetings"]
        counts: dict[str, Any] = {}
        for t in tables:
            counts[t] = _safe_count(conn, t)

        sf = conn.execute(
            "SELECT SUM(CASE WHEN home_score IS NOT NULL THEN 1 ELSE 0 END) AS settled,"
            " SUM(CASE WHEN home_score IS NULL THEN 1 ELSE 0 END) AS unsettled FROM fixtures"
        ).fetchone()
        counts["fixtures_settled"]   = int(sf["settled"]   or 0) if sf else 0
        counts["fixtures_unsettled"] = int(sf["unsettled"] or 0) if sf else 0

        es = conn.execute(
            "SELECT SUM(CASE WHEN f.home_score IS NOT NULL THEN 1 ELSE 0 END) AS settled,"
            " SUM(CASE WHEN f.home_score IS NULL THEN 1 ELSE 0 END) AS unsettled "
            "FROM emit_log em JOIN fixtures f ON f.id = em.fixture_id"
        ).fetchone()
        counts["emit_settled"]   = int(es["settled"]   or 0) if es else 0
        counts["emit_unsettled"] = int(es["unsettled"] or 0) if es else 0

        latest = conn.execute("SELECT MAX(date) FROM fixtures").fetchone()
    finally:
        conn.close()

    return {
        "counts":         counts,
        "latest_fixture": latest[0] if latest else None,
        "as_of":          datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /diagnostics/odds_coverage
# ---------------------------------------------------------------------------

@router.get("/odds_coverage")
def odds_coverage() -> dict[str, Any]:
    """Per-league odds coverage statistics."""
    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            """
            SELECT lg.name, lg.tier,
                   COUNT(*) AS total,
                   SUM(CASE WHEN f.goals_over_15_odd IS NOT NULL THEN 1 ELSE 0 END) AS goal_n,
                   SUM(CASE WHEN f.btts_yes_odd IS NOT NULL THEN 1 ELSE 0 END) AS bts_n,
                   SUM(CASE WHEN f.corners_over_85_odd IS NOT NULL THEN 1 ELSE 0 END) AS corner_n
            FROM fixtures f
            JOIN leagues lg ON lg.id = f.league_id
            GROUP BY lg.id
            ORDER BY total DESC
            """
        ).fetchall()
    finally:
        conn.close()

    leagues = []
    for r in rows:
        total = r["total"] or 1
        leagues.append({
            "name":          r["name"],
            "tier":          r["tier"],
            "total":         r["total"],
            "goal_odds_pct":   round(r["goal_n"] / total * 100, 1),
            "bts_odds_pct":    round(r["bts_n"]  / total * 100, 1),
            "corner_odds_pct": round(r["corner_n"] / total * 100, 1),
            "asian_odds_pct":  None,
        })
    return {"as_of": datetime.now(tz=timezone.utc).isoformat(), "leagues": leagues}


# ---------------------------------------------------------------------------
# GET /diagnostics/cron/heartbeat
# ---------------------------------------------------------------------------

@router.get("/cron/heartbeat")
def cron_heartbeat() -> dict[str, Any]:
    """Last pipeline heartbeat in system_health (any of the 12 daily tasks).

    V3.1 (2026-05-28): broadened from `cron_heartbeat` only to any pipeline
    metric. `metric` in the response identifies which task last reported.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        row = _latest_pipeline_row(conn)
    except Exception:
        row = None
    finally:
        conn.close()

    if not row:
        return {"recorded_at": None, "value": None, "metric": None, "stale": True}

    now = datetime.now(tz=timezone.utc)
    try:
        ts = datetime.fromisoformat((row["recorded_at"] or "").replace(" ", "T"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_h = (now - ts).total_seconds() / 3600
        stale = age_h > 26
    except Exception:
        stale = True

    return {
        "recorded_at": row["recorded_at"],
        "value":       row["value"],
        "metric":      row["metric"],
        "stale":       stale,
    }


# ---------------------------------------------------------------------------
# GET /diagnostics/drift_report  (Stats tab)
# ---------------------------------------------------------------------------

@router.get("/drift_report")
def drift_report() -> dict[str, Any]:
    """Partition-level drift summary for the Stats tab."""
    conn = get_conn(settings.sqlite_path)
    try:
        from app.api.routes_inspector import compute_drift_rows
        rows = compute_drift_rows(conn, recent_days=30)
    finally:
        conn.close()

    ok = sum(1 for r in rows if r["flag"] == "stable")
    warning = sum(1 for r in rows if r["flag"] == "watch")
    critical = sum(1 for r in rows if r["flag"] == "drifting")

    now = datetime.now(tz=timezone.utc)
    partitions = [
        {
            "partition_key": f"{r['zone']}:{r.get('df') or '-'}:{r['bts_v2']}",
            "class":         "promote",
            "n_current":     r["recent_n"],
            "edge_current":  None,
            "hw_level":      None,
            "hw_trend":      None,
            "wilson_95_lb":  None,
            "conc_drop_pp":  None,
            "history_buckets": 1,
            "flag": ("ok" if r["flag"] == "stable" else
                     "warning" if r["flag"] == "watch" else
                     "critical" if r["flag"] == "drifting" else "ok"),
        }
        for r in rows
    ]
    return {
        "snapshot_taken_at": now.isoformat(),
        "summary": {"ok": ok, "warning": warning, "critical": critical},
        "partitions": partitions,
    }


# ---------------------------------------------------------------------------
# GET /diagnostics/activity_by_tier  (Stats tab)
# ---------------------------------------------------------------------------

@router.get("/activity_by_tier")
def activity_by_tier(days: int = Query(7, ge=1, le=365)) -> dict[str, Any]:
    """Per-tier engine activity over the last N days."""
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn(settings.sqlite_path)
    try:
        emit_rows = conn.execute(
            """SELECT lg.tier, COUNT(*) AS n
               FROM emit_log em
               JOIN fixtures f ON f.id = em.fixture_id
               LEFT JOIN leagues lg ON lg.id = f.league_id
               WHERE em.emitted_at >= ?
               GROUP BY lg.tier""",
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()

    def _tier_key(t: Any) -> str:
        return f"T{t}" if t in (1, 2, 3) else "untiered"

    tier_data: dict[str, dict] = {}
    for r in emit_rows:
        tk = _tier_key(r["tier"])
        tier_data[tk] = {
            "tier_key": tk, "tier": r["tier"],
            "emit": r["n"], "lock": 0, "pass": 0,
            "settled": 0, "stake_zar": 0.0, "pnl_zar": 0.0,
        }

    return {
        "window_days": days,
        "tiers":       list(tier_data.values()),
    }


# ---------------------------------------------------------------------------
# GET /healthz/deep  (health badge in the SPA)
# ---------------------------------------------------------------------------

@router.get("/healthz_deep", include_in_schema=False)
def healthz_deep_alias() -> dict[str, Any]:
    return _healthz_deep_impl()


def _healthz_deep_impl() -> dict[str, Any]:
    from app.settings import settings as _s
    conn = get_conn(_s.sqlite_path)
    try:
        fx_count = _safe_count(conn, "fixtures") or 0
        emit_count = _safe_count(conn, "emit_log") or 0
    finally:
        conn.close()

    env = getattr(settings, "app_env", "local")
    return {
        "status": "ok",
        "env":    env,
        "db": {
            "fixtures": fx_count,
            "emit_log": emit_count,
        },
    }
