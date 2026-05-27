"""OddsFlow V3 — League upsert from Sportmonks subscription list.

Upserts all 30 subscribed leagues with their sportmonks_id and tier.
Matches existing rows by name+country; inserts new ones.
Safe to re-run — idempotent.

Usage:
    python scripts/update_leagues.py
"""

import sqlite3

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"

# Complete league subscription from API provider.
# Format: (sportmonks_id, country, name, tier)
LEAGUES = [
    # T1 — top-flight leagues
    (573,  "Sweden",              "Allsvenskan",                 1),
    (444,  "Norway",              "Eliteserien",                 1),
    (345,  "Iceland",             "Besta deild",                 1),
    (292,  "Finland",             "Veikkausliiga",               1),
    (360,  "Republic of Ireland", "Premier Division",            1),
    (779,  "United States",       "Major League Soccer",         1),
    (648,  "Brazil",              "Serie A",                     1),
    (3537, "Japan",               "J1 100 Year Vision League",   1),
    (1034, "South Korea",         "K League 1",                  1),
    # T2 — second-tier / strong regional leagues
    (393,  "Kazakhstan",          "Premier League",              2),
    (405,  "Lithuania",           "A Lyga",                      2),
    (579,  "Sweden",              "Superettan",                  2),
    (585,  "Sweden",              "Ettan: North",                2),
    (588,  "Sweden",              "Ettan: South",                2),
    (681,  "Colombia",            "Copa Colombia",               2),
    (678,  "Colombia",            "Primera B",                   2),
    (696,  "Ecuador",             "Liga Pro",                    2),
    (1689, "Canada",              "Premier League",              2),
    (295,  "Finland",             "Ykköseliga",                  2),
    (286,  "Estonia",             "Meistriliiga",                2),
    (289,  "Estonia",             "Esiliiga A",                  2),
    (791,  "United States",       "USL Championship",            2),
    (3550, "Japan",               "J2/J3 100 Year Vision League",2),
    (989,  "China",               "Super League",                2),
    # T3 — lower tiers / development leagues
    (1642, "Argentina",           "Reserve League",              3),
    (351,  "Iceland",             "2. Deild",                    3),
    (797,  "United States",       "USL League Two",              3),
    (1607, "United States",       "USL League One",              3),
    (2545, "United States",       "MLS Next Pro",                3),
    (1098, "Bolivia",             "Liga De Futbol Prof",         3),
]


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    inserted = updated = 0

    for sm_id, country, name, tier in LEAGUES:
        # Check if row already has this sportmonks_id
        existing_by_smid = conn.execute(
            "SELECT id FROM leagues WHERE sportmonks_id = ?", (sm_id,)
        ).fetchone()

        if existing_by_smid:
            conn.execute(
                "UPDATE leagues SET country=?, name=?, tier=? WHERE sportmonks_id=?",
                (country, name, tier, sm_id),
            )
            updated += 1
            continue

        # Try matching by country+name (case-insensitive)
        existing_by_name = conn.execute(
            "SELECT id FROM leagues WHERE lower(country)=lower(?) AND lower(name)=lower(?)",
            (country, name),
        ).fetchone()

        if existing_by_name:
            conn.execute(
                "UPDATE leagues SET sportmonks_id=?, tier=? WHERE id=?",
                (sm_id, tier, existing_by_name["id"]),
            )
            updated += 1
        else:
            conn.execute(
                "INSERT INTO leagues (sportmonks_id, country, name, tier) VALUES (?,?,?,?)",
                (sm_id, country, name, tier),
            )
            inserted += 1

    conn.commit()
    conn.close()

    print(f"Done — inserted={inserted}  updated={updated}")
    print(f"Total subscription leagues: {len(LEAGUES)}")


if __name__ == "__main__":
    main()
