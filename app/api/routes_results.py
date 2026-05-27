"""OddsFlow V4 — Results display and livescores proxy.

GET /api/results       — recent settled fixtures from DB (history view)
GET /api/livescores    — Sportmonks inplay proxy; auto-writes finished scores + settles picks
"""
from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.api.routes_picks import settle_pick
from app.db.database import get_conn
from app.settings import settings

router = APIRouter(tags=["results"])

_TOKEN = "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN"
_BASE  = "https://api.sportmonks.com/v3/football"

ACTIVE_LEAGUES = {
    8, 301, 564, 384, 573, 444, 345, 292, 360, 779, 648, 3537, 1034,
    567, 579, 585, 588, 681, 678, 696, 1689, 295, 286, 289, 791, 3550, 989,
    1607, 2545, 1098,
}

# Sportmonks state short_name / developer_name values that indicate FT
_FINISHED = {"FT", "AET", "FT_PEN", "FINISHED", "AWARDED"}


def _sm_get(path: str, params: dict) -> dict:
    params["api_token"] = _TOKEN
    url = f"{_BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as r:
        return json.loads(r.read())


def _parse_scores(scores_list: list) -> tuple[int | None, int | None]:
    home = away = None
    for s in (scores_list or []):
        if s.get("description") != "CURRENT":
            continue
        sd = s.get("score") or {}
        g  = sd.get("goals")
        p  = sd.get("participant")
        if g is None:
            continue
        try:
            g = int(g)
        except (TypeError, ValueError):
            continue
        if p == "home":
            home = g
        elif p == "away":
            away = g
    return home, away


def _write_and_settle(
    conn: sqlite3.Connection,
    fixture_db_id: int,
    home_score: int,
    away_score: int,
    now_ts: str,
) -> tuple[int, int]:
    """Write scores + settle pending picks for one fixture. Returns (rows_written, picks_settled)."""
    cur = conn.execute("""
        UPDATE fixtures SET
            home_score=?, away_score=?, total_goals=?,
            status='settled', updated_at=?
        WHERE id=? AND home_score IS NULL
    """, (home_score, away_score, home_score + away_score, now_ts, fixture_db_id))
    written = cur.rowcount

    settled_n = 0
    if written:
        pending = conn.execute("""
            SELECT em.pick_uuid, em.market, em.pick,
                   f.home_odd, f.away_odd,
                   fs.total_corners
            FROM emit_log em
            JOIN fixtures f ON f.id = em.fixture_id
            LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
            WHERE em.fixture_id = ?
              AND NOT EXISTS (SELECT 1 FROM pick_results pr WHERE pr.pick_uuid = em.pick_uuid)
        """, (fixture_db_id,)).fetchall()
        for row in pending:
            # V3.1 (2026-05-28): pass pick + total_corners for corners_nl.
            val = settle_pick(row["market"], home_score, away_score,
                              row["home_odd"], row["away_odd"],
                              row["pick"] or "", total_corners=row["total_corners"])
            if val is None:
                continue
            lbl = "WIN" if val == 1.0 else "VOID" if val == 0.5 else "LOSS"
            conn.execute("""
                INSERT OR IGNORE INTO pick_results (pick_uuid, settled_at, outcome, actual_value)
                VALUES (?, ?, ?, ?)
            """, (row["pick_uuid"], now_ts, lbl, val))
            settled_n += 1

    return written, settled_n


# ---------------------------------------------------------------------------
# GET /api/results
# ---------------------------------------------------------------------------

@router.get("/api/results")
def get_results(
    days: int = Query(7, ge=1, le=90),
    league_id: int | None = Query(None),
) -> dict[str, Any]:
    """Recently settled fixtures from the DB with pick-outcome overlay."""
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_conn(settings.sqlite_path)
    try:
        q = """
            SELECT f.id, f.date,
                   COALESCE(f.home_team_name, th.name) AS home_team_name,
                   COALESCE(f.away_team_name, ta.name) AS away_team_name,
                   f.home_score, f.away_score, f.total_goals,
                   f.draw_zone, f.df_level, f.bts_pocket, f.tier,
                   fs.home_corners, fs.away_corners, fs.total_corners,
                   lg.name AS league_name, lg.country,
                   em.pick_uuid, em.market, em.pick, em.pick_odd AS emit_odd,
                   pr.outcome, pr.actual_value
            FROM fixtures f
            LEFT JOIN fixture_stats fs  ON fs.fixture_id = f.id
            LEFT JOIN leagues lg        ON lg.id = f.league_id
            LEFT JOIN teams th          ON th.id = f.home_team_id
            LEFT JOIN teams ta          ON ta.id = f.away_team_id
            LEFT JOIN emit_log em       ON em.fixture_id = f.id
            LEFT JOIN pick_results pr   ON pr.pick_uuid = em.pick_uuid
            WHERE f.home_score IS NOT NULL
              AND substr(f.date, 1, 10) >= ?
        """
        args: list[Any] = [cutoff]
        if league_id is not None:
            q += " AND f.league_id = ?"
            args.append(league_id)
        q += " ORDER BY f.date DESC, f.id, em.pick_uuid"

        rows = conn.execute(q, args).fetchall()
    finally:
        conn.close()

    fx_map: dict[int, dict] = {}
    for r in rows:
        fid = r["id"]
        if fid not in fx_map:
            fx_map[fid] = {
                "fixture_id":    fid,
                "date":          r["date"],
                "home_team":     r["home_team_name"],
                "away_team":     r["away_team_name"],
                "home_score":    r["home_score"],
                "away_score":    r["away_score"],
                "total_goals":   r["total_goals"],
                "home_corners":  r["home_corners"],
                "away_corners":  r["away_corners"],
                "total_corners": r["total_corners"],
                "league":        r["league_name"],
                "country":       r["country"],
                "tier":          r["tier"],
                "draw_zone":     r["draw_zone"],
                "bts_pocket":    r["bts_pocket"],
                "picks":         [],
            }
        if r["pick_uuid"]:
            fx_map[fid]["picks"].append({
                "pick_uuid":    r["pick_uuid"],
                "market":       r["market"],
                "pick":         r["pick"],
                "pick_odd":     r["emit_odd"],
                "outcome":      r["outcome"],
                "actual_value": r["actual_value"],
            })

    return {
        "as_of":       datetime.now(tz=timezone.utc).isoformat(),
        "window_days": days,
        "count":       len(fx_map),
        "fixtures":    list(fx_map.values()),
    }


# ---------------------------------------------------------------------------
# GET /api/livescores
# ---------------------------------------------------------------------------

@router.get("/api/livescores")
def get_livescores() -> dict[str, Any]:
    """Proxy Sportmonks inplay livescores filtered to active leagues.
    For any fixture in the DB that appears finished here with home_score IS NULL,
    the score is written and pending picks are settled automatically.
    """
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        data = _sm_get("livescores/inplay", {
            "include": "scores;participants;state",
            "per_page": 100,
        })
    except Exception as exc:
        return {"error": str(exc), "fixtures": [], "as_of": now_ts,
                "auto_written": 0, "auto_settled": 0}

    raw    = data.get("data") or []
    active = [fx for fx in raw if fx.get("league_id") in ACTIVE_LEAGUES]

    fixtures_out = []
    to_write: list[tuple[int, int, int]] = []   # (sm_id, home_score, away_score)

    for fx in active:
        sm_id  = fx.get("id")
        state  = fx.get("state") or {}
        status = (state.get("short_name") or state.get("developer_name") or "").upper()
        minute = fx.get("minute")

        participants = fx.get("participants") or []
        home_team = next(
            (p.get("name") for p in participants if p.get("meta", {}).get("location") == "home"),
            None,
        )
        away_team = next(
            (p.get("name") for p in participants if p.get("meta", {}).get("location") == "away"),
            None,
        )

        home_score, away_score = _parse_scores(fx.get("scores") or [])

        fixtures_out.append({
            "sportmonks_id": sm_id,
            "league_id":     fx.get("league_id"),
            "home_team":     home_team,
            "away_team":     away_team,
            "home_score":    home_score,
            "away_score":    away_score,
            "status":        status,
            "minute":        minute,
        })

        if status in _FINISHED and home_score is not None and away_score is not None and sm_id:
            to_write.append((int(sm_id), home_score, away_score))

    written = settled = 0
    if to_write:
        conn = sqlite3.connect(settings.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            for sm_id, hs, aws in to_write:
                db_row = conn.execute(
                    "SELECT id FROM fixtures WHERE sportmonks_id=? AND home_score IS NULL",
                    (sm_id,),
                ).fetchone()
                if db_row is None:
                    continue
                w, s = _write_and_settle(conn, db_row["id"], hs, aws, now_ts)
                written += w
                settled += s
            conn.commit()
        finally:
            conn.close()

    return {
        "as_of":        now_ts,
        "count":        len(fixtures_out),
        "auto_written": written,
        "auto_settled": settled,
        "fixtures":     fixtures_out,
    }
