"""Settle pending picks in emit_log against fixture scores.

Run after fetch_upcoming.py or whenever fixture scores may have updated.
Writes unsettled emit_log rows (where fixture has a result) to pick_results.
"""
import sqlite3
from datetime import datetime, timezone

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"


def settle_pick(market: str, home_score, away_score, home_odd, away_odd):
    if home_score is None or away_score is None or home_odd is None or away_odd is None:
        return None
    alpha_home = home_odd <= away_odd
    alpha_wins = (home_score > away_score) if alpha_home else (away_score > home_score)
    draw = (home_score == away_score)
    if market == "dnb":
        return 1.0 if alpha_wins else (0.5 if draw else 0.0)
    if market == "alpha_win":
        return 1.0 if alpha_wins else 0.0
    return None


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

# Find emit_log entries for settled fixtures with no pick_results row yet
rows = conn.execute("""
    SELECT em.pick_uuid, em.market, em.pick,
           f.home_score, f.away_score, f.home_odd, f.away_odd, f.date
    FROM emit_log em
    JOIN fixtures f ON f.id = em.fixture_id
    WHERE f.home_score IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM pick_results pr WHERE pr.pick_uuid = em.pick_uuid
      )
""").fetchall()

print(f"Unsettled picks ready for settlement: {len(rows)}")

settled = skipped = 0
for r in rows:
    outcome = settle_pick(r["market"], r["home_score"], r["away_score"],
                          r["home_odd"], r["away_odd"])
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
