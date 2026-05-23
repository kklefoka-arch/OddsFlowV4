"""Backfill draw_zone and bts_pocket on all classifiable fixtures.

Reads draw_odd, btts_yes_odd, btts_no_odd from every fixture and writes
draw_zone and bts_pocket in-place. Idempotent — safe to re-run.

Run once after migrate_cleanup_ghosts.py.
After this, fetch_upcoming.py will write zone/bts on every insert/update.
"""
import sqlite3
import sys

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"


def zone_of(draw_odd):
    if draw_odd is None:
        return None
    if draw_odd < 2.70:
        return None
    if draw_odd < 3.40:
        return "strong"
    if draw_odd < 4.10:
        return "standard"
    if draw_odd < 4.80:
        return "low"
    return "one_sided"


def bts_of(yes_odd, no_odd):
    if yes_odd is None or no_odd is None:
        return None
    yes_favoured = yes_odd <= no_odd
    if yes_favoured:
        return "strong_over" if yes_odd < 1.50 else "slight_over"
    else:
        return "strong_under" if no_odd < 1.50 else "slight_under"


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT id, draw_odd, btts_yes_odd, btts_no_odd
    FROM fixtures
    WHERE draw_odd IS NOT NULL
      AND btts_yes_odd IS NOT NULL
      AND btts_no_odd IS NOT NULL
""").fetchall()

print(f"Classifiable fixtures: {len(rows)}")

updated = skipped = 0
for row in rows:
    zone = zone_of(row["draw_odd"])
    bts  = bts_of(row["btts_yes_odd"], row["btts_no_odd"])
    if zone is None or bts is None:
        skipped += 1
        continue
    conn.execute(
        "UPDATE fixtures SET draw_zone=?, bts_pocket=? WHERE id=?",
        (zone, bts, row["id"]),
    )
    updated += 1

conn.commit()
conn.close()

print(f"Updated: {updated}  Skipped (excluded zone): {skipped}")
print()

# Verification
conn2 = sqlite3.connect(DB)
dist  = conn2.execute("""
    SELECT draw_zone, COUNT(*) as n
    FROM fixtures
    WHERE draw_zone IS NOT NULL
    GROUP BY draw_zone
    ORDER BY draw_zone
""").fetchall()
print("Zone distribution after backfill:")
for r in dist:
    print(f"  {r[0]}: {r[1]}")
conn2.close()
