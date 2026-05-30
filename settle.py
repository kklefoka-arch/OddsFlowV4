"""Settle pending picks in emit_log against fixture scores.

Run after fetch_results.py whenever fixture scores may have updated.
Writes unsettled emit_log rows (where fixture has a result) to pick_results.

Markets handled: threeway (alpha-or-draw, no void), goals_nl, corners_nl,
plus legacy dnb / alpha_win for emit_log rows predating the Re-Foundation.
"""
import re
import sqlite3
from datetime import datetime, timezone

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"


def settle_pick(market: str, home_score, away_score, home_odd, away_odd,
                pick: str = "", total_corners=None):
    if home_score is None or away_score is None:
        return None

    if market == "goals_nl":
        m = re.match(r"Over (\d+\.5) Goals", pick or "")
        if not m:
            return None
        line = float(m.group(1))
        return 1.0 if (home_score + away_score) > line else 0.0

    if market == "corners_nl":
        m = re.match(r"Over (\d+\.5) Corners", pick or "")
        if not m:
            return None
        line = float(m.group(1))
        if total_corners is None:
            return None
        return 1.0 if total_corners > line else 0.0

    if market in ("threeway", "dnb", "alpha_win"):
        if home_odd is None or away_odd is None:
            return None
        alpha_home = home_odd <= away_odd
        alpha_wins = (home_score > away_score) if alpha_home else (away_score > home_score)
        draw = (home_score == away_score)
        # threeway = ground-zero "alpha-or-draw": a draw is a protected WIN (no 0.5 void).
        if market == "threeway":
            return 1.0 if (alpha_wins or draw) else 0.0
        # legacy markets (pre-Re-Foundation emit_log rows still pending):
        if market == "dnb":
            return 1.0 if alpha_wins else (0.5 if draw else 0.0)
        return 1.0 if alpha_wins else 0.0   # legacy alpha_win

    return None


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

rows = conn.execute("""
    SELECT em.pick_uuid, em.market, em.pick,
           f.home_score, f.away_score, f.home_odd, f.away_odd, f.date,
           CASE
             WHEN fs.home_corners IS NOT NULL AND fs.away_corners IS NOT NULL
             THEN fs.home_corners + fs.away_corners
             ELSE NULL
           END AS total_corners
    FROM emit_log em
    JOIN fixtures f ON f.id = em.fixture_id
    LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
    WHERE f.home_score IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM pick_results pr WHERE pr.pick_uuid = em.pick_uuid
      )
""").fetchall()

print(f"Unsettled picks ready for settlement: {len(rows)}")

settled = skipped = 0
for r in rows:
    outcome = settle_pick(
        r["market"], r["home_score"], r["away_score"],
        r["home_odd"], r["away_odd"],
        r["pick"], r["total_corners"],
    )
    if outcome is None:
        skipped += 1
        continue
    lbl = "WIN" if outcome == 1.0 else "VOID" if outcome == 0.5 else "LOSS"
    conn.execute("""
        INSERT OR IGNORE INTO pick_results (pick_uuid, settled_at, outcome, actual_value)
        VALUES (?, ?, ?, ?)
    """, (r["pick_uuid"], now_ts, lbl, outcome))
    settled += 1

conn.execute(
    "INSERT INTO system_health (metric, value) VALUES (?, ?)",
    ("settle", f"ok: {settled} settled, {skipped} skipped"),
)
conn.commit()
conn.close()
print(f"Done — settled={settled}  skipped={skipped}")
