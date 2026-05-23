import sqlite3
conn = sqlite3.connect(r"C:\OddsFlowV4\data\oddsflow_v4.db")
conn.row_factory = sqlite3.Row

print("=== Leagues table ===")
rows = conn.execute("SELECT id, sportmonks_id, name, country FROM leagues LIMIT 15").fetchall()
for r in rows:
    print(dict(r))

print("\n=== Distinct fixture league_ids ===")
rows = conn.execute("SELECT DISTINCT league_id FROM fixtures ORDER BY league_id LIMIT 30").fetchall()
print([r[0] for r in rows])

print("\n=== Match via sportmonks_id ===")
r = conn.execute("""
    SELECT COUNT(*) as cnt FROM fixtures f
    JOIN leagues l ON l.sportmonks_id = f.league_id
    WHERE f.home_score IS NULL AND f.date >= date('now')
""").fetchone()
print("Via sportmonks_id:", r[0])

r2 = conn.execute("""
    SELECT COUNT(*) as cnt FROM fixtures f
    JOIN leagues l ON l.id = f.league_id
    WHERE f.home_score IS NULL AND f.date >= date('now')
""").fetchone()
print("Via id:", r2[0])

conn.close()
