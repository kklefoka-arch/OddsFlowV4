"""One-shot: apply Re-Foundation country-context tier corrections to the DB.

Run ONCE at cutover (after the code lands on master). Idempotent.

1. Correct tiers in `leagues` (by sportmonks_id) to the country-context map.
2. Backfill name/country for the 5 historical "Unknown" leagues (by internal id).
3. Sync `fixtures.tier` from `leagues.tier` so the T1+T2 vs T3 split is correct.

Tier only affects display/grouping, not emission — the ground-zero policy is
per (zone, bts) and tier-agnostic.
"""
import sqlite3

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"

# (sportmonks_id, new_tier) — country-context corrections.
TIER_CORRECTIONS = [
    (989, 1),   # China Super League        T2->T1 (top flight)
    (1098, 1),  # Bolivia Liga De Futbol    T3->T1 (top flight)
    (696, 1),   # Ecuador Liga Pro          T2->T1
    (1689, 1),  # Canada Premier League     T2->T1
    (286, 1),   # Estonia Meistriliiga      T2->T1
    (393, 1),   # Kazakhstan Premier League T2->T1
    (405, 1),   # Lithuania A Lyga          T2->T1
    (585, 3),   # Sweden Ettan: North       T2->T3 (3rd tier)
    (588, 3),   # Sweden Ettan: South       T2->T3 (3rd tier)
    (681, 3),   # Colombia Copa Colombia    T2->T3 (cup)
]

# (internal leagues.id, country, name) — backfill historical "Unknown" leagues.
# Tiers already correct (74/543/947=T2, 1203/1205=T3); names/country only.
UNKNOWN_BACKFILL = [
    (74,   "Netherlands", "Eerste Divisie"),
    (543,  "Slovakia",    "2. Liga"),
    (947,  "Saudi Arabia","First Division League"),
    (1203, "Italy",       "Serie C — Girone A"),
    (1205, "Italy",       "Serie C — Girone C"),
]


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    changed = 0

    for sm_id, tier in TIER_CORRECTIONS:
        cur = con.execute("UPDATE leagues SET tier=? WHERE sportmonks_id=? AND tier IS NOT ?",
                          (tier, sm_id, tier))
        if cur.rowcount:
            changed += cur.rowcount
            print(f"  leagues: sportmonks_id={sm_id} -> tier {tier}")

    for lid, country, name in UNKNOWN_BACKFILL:
        cur = con.execute("UPDATE leagues SET country=?, name=? WHERE id=?",
                          (country, name, lid))
        if cur.rowcount:
            print(f"  leagues: id={lid} -> {country} / {name}")

    # Sync fixtures.tier from leagues.tier (only where the league is known).
    cur = con.execute("""
        UPDATE fixtures
           SET tier = (SELECT l.tier FROM leagues l WHERE l.id = fixtures.league_id)
         WHERE league_id IN (SELECT id FROM leagues WHERE tier IS NOT NULL)
    """)
    print(f"  fixtures.tier synced from leagues.tier: {cur.rowcount} rows")

    con.execute("INSERT INTO system_health (metric, value) VALUES (?, ?)",
                ("refoundation_tier_fix", f"ok: {changed} league tier corrections applied"))
    con.commit()

    # Report new T1+T2 vs T3 settled counts.
    for grp, where in (("T1+T2", "tier IN (1,2)"), ("T3", "tier=3")):
        n = con.execute(f"SELECT COUNT(*) FROM fixtures WHERE home_score IS NOT NULL AND {where}").fetchone()[0]
        print(f"  settled {grp}: {n}")
    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
