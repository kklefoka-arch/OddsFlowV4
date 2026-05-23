"""Remove ghost fixture rows — upcoming fixtures with no sportmonks_id and no score.

These were seeded by the V2/V3 historical pipeline with no Sportmonks reference.
They have no odds, no pick eligibility, and cannot be updated by fetch_upcoming.py.
Historical rows (sportmonks_id IS NULL but home_score IS NOT NULL) are kept —
they contribute to the foundation matrix.

Run once. Safe to re-run — deletes 0 rows if already cleaned.
"""
import sqlite3

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"

conn = sqlite3.connect(DB)

to_delete = conn.execute("""
    SELECT COUNT(*) FROM fixtures
    WHERE sportmonks_id IS NULL
      AND home_score IS NULL
""").fetchone()[0]

print(f"Ghost upcoming fixtures (sportmonks_id=NULL, home_score=NULL): {to_delete}")

if to_delete == 0:
    print("Nothing to delete — already clean.")
    conn.close()
    raise SystemExit(0)

print("Proceeding with delete...")
conn.execute("""
    DELETE FROM fixtures
    WHERE sportmonks_id IS NULL
      AND home_score IS NULL
""")
conn.commit()

remaining = conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]
settled   = conn.execute("SELECT COUNT(*) FROM fixtures WHERE home_score IS NOT NULL").fetchone()[0]
upcoming  = conn.execute("SELECT COUNT(*) FROM fixtures WHERE home_score IS NULL").fetchone()[0]

conn.close()

print(f"Deleted: {to_delete}")
print(f"Remaining fixtures: {remaining}  ({settled} settled, {upcoming} upcoming)")
