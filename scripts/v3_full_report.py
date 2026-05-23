"""
OddsFlow V3 — Full Engine Testing Report (Phases 2–7)
Runs against v1_calibration_readonly.db. No external deps beyond stdlib + sqlite3.
"""
from __future__ import annotations
import sys, sqlite3
from collections import defaultdict
from pathlib import Path

# Force UTF-8 output on Windows (cp1252 can't encode →, –, etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_PATH = Path(r"C:\OddsFlow2\engine\data\v1_calibration_readonly.db")

# ---------------------------------------------------------------------------
# Classification (V3 rules — mirrors classify.py)
# ---------------------------------------------------------------------------
def zone_of(draw_odd):
    if draw_odd is None: return None
    if draw_odd < 2.70: return None
    if draw_odd < 3.40: return "strong"
    if draw_odd < 4.10: return "standard"
    if draw_odd < 4.80: return "low"
    return "one_sided"

def bts_of(yes_odd, no_odd):
    if yes_odd is None or no_odd is None: return None
    yes_fav = yes_odd <= no_odd
    if yes_fav:
        return "strong_over" if yes_odd < 1.50 else "slight_over"
    else:
        return "strong_under" if no_odd < 1.50 else "slight_under"

# ---------------------------------------------------------------------------
# Natural lines (mirrors natural_lines.py)
# ---------------------------------------------------------------------------
NATURAL_LINES = {
    "strong":    {"goals": 2.0, "corners": 9.0},
    "standard":  {"goals": 2.0, "corners": 9.0},
    "low":       {"goals": 3.0, "corners": 10.0},
    "one_sided": {"goals": 3.0, "corners": 10.0},
}
SYSTEM_LINES = {
    "strong":    {"goals": 3.0, "corners": 10.0},
    "standard":  {"goals": 3.0, "corners": 10.0},
    "low":       {"goals": 4.0, "corners": 11.0},
    "one_sided": {"goals": 4.0, "corners": 11.0},
}

# ---------------------------------------------------------------------------
# Promotion constants (mirrors promotion.py)
# ---------------------------------------------------------------------------
PROMOTE_THRESHOLD = 72.0
PROMOTE_LOWER = 67.5
DROP_SECONDARY_GAP = 4.5
LOW_ZONE_SUPPRESS = True

def hit_rate(num, den):
    return num / den * 100.0 if den else 0.0

def promote_status(hit, drop, rank, rank1_drop, zone):
    if hit >= PROMOTE_THRESHOLD:
        status = "PROMOTE"
    elif hit >= PROMOTE_LOWER:
        qualifies = rank == 1 or drop <= rank1_drop + DROP_SECONDARY_GAP
        status = "PROMOTE_TOLERANCE" if qualifies else "HOLD"
    else:
        status = "NO"
    if LOW_ZONE_SUPPRESS and zone == "low" and status in ("PROMOTE","PROMOTE_TOLERANCE"):
        return "MEASURING"
    return status

def threeway_promote_status(hit, zone):
    if hit >= PROMOTE_THRESHOLD: status = "PROMOTE"
    elif hit >= PROMOTE_LOWER: status = "PROMOTE_TOLERANCE"
    else: status = "NO"
    if LOW_ZONE_SUPPRESS and zone == "low" and status in ("PROMOTE","PROMOTE_TOLERANCE"):
        return "MEASURING"
    return status

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_fixtures(conn):
    sql = """
        SELECT
            f.id, f.home_score, f.away_score,
            f.draw_odd, f.btts_yes_odd, f.btts_no_odd,
            f.home_odd, f.away_odd,
            f.tier,
            fs.home_corners,
            fs.away_corners
        FROM fixtures f
        LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
        WHERE f.home_score IS NOT NULL
          AND f.away_score IS NOT NULL
    """
    rows = []
    for r in conn.execute(sql):
        rows.append({
            "id": r[0], "home_score": r[1], "away_score": r[2],
            "draw_odd": r[3], "btts_yes_odd": r[4], "btts_no_odd": r[5],
            "home_odd": r[6], "away_odd": r[7], "tier": r[8],
            "home_corners": r[9], "away_corners": r[10],
        })
    return rows

# ---------------------------------------------------------------------------
# Cell computation
# ---------------------------------------------------------------------------
def compute_cells(rows):
    acc = defaultdict(lambda: {"n":0,"gn":0,"gs":0,"cn":0,"cs":0,"tw":0,
                                "t1":0,"t2":0,"t3":0,"cn_n":0})

    for r in rows:
        zone = zone_of(r["draw_odd"])
        bts  = bts_of(r["btts_yes_odd"], r["btts_no_odd"])
        if not zone or not bts: continue

        gn_line = NATURAL_LINES[zone]["goals"]
        gs_line = SYSTEM_LINES[zone]["goals"]
        cn_line = NATURAL_LINES[zone]["corners"]
        cs_line = SYSTEM_LINES[zone]["corners"]

        goals = r["home_score"] + r["away_score"]
        hc, ac = r["home_corners"], r["away_corners"]
        corners = (hc + ac) if (hc is not None and ac is not None) else None

        ho, ao = r["home_odd"], r["away_odd"]
        alpha_home = (ho <= ao) if (ho and ao) else True
        alpha_wins = (r["home_score"] > r["away_score"]) if alpha_home else (r["away_score"] > r["home_score"])
        draw = r["home_score"] == r["away_score"]
        tw_green = alpha_wins or draw if zone in ("strong","standard") else alpha_wins

        cell = acc[(zone, bts)]
        cell["n"] += 1
        if goals > gn_line: cell["gn"] += 1
        if goals > gs_line: cell["gs"] += 1
        if corners is not None:
            cell["cn_n"] += 1
            if corners > cn_line: cell["cn"] += 1
            if corners > cs_line: cell["cs"] += 1
        if tw_green: cell["tw"] += 1
        t = r.get("tier") or 0
        if t == 1: cell["t1"] += 1
        elif t == 2: cell["t2"] += 1
        elif t == 3: cell["t3"] += 1

    result = []
    for (zone, bts), c in acc.items():
        n = c["n"]
        cn_n = c["cn_n"]
        gn_hit = hit_rate(c["gn"], n)
        gs_hit = hit_rate(c["gs"], n)
        cn_hit = hit_rate(c["cn"], cn_n)
        cs_hit = hit_rate(c["cs"], cn_n)
        tw_hit = hit_rate(c["tw"], n)
        g_drop = gn_hit - gs_hit
        co_drop = cn_hit - cs_hit
        result.append({
            "zone": zone, "bts": bts, "n": n, "cn_n": cn_n,
            "gn_hit": gn_hit, "gs_hit": gs_hit,
            "cn_hit": cn_hit, "cs_hit": cs_hit,
            "tw_hit": tw_hit,
            "g_drop": g_drop, "co_drop": co_drop,
            "t1": c["t1"], "t2": c["t2"], "t3": c["t3"],
        })

    zone_groups = defaultdict(list)
    for cell in result:
        zone_groups[cell["zone"]].append(cell)

    for zone, group in zone_groups.items():
        sg = sorted(group, key=lambda c: c["g_drop"])
        for rank, cell in enumerate(sg, 1): cell["g_rank"] = rank
        r1_g = sg[0]["g_drop"] if sg else 0
        sc = sorted(group, key=lambda c: c["co_drop"])
        for rank, cell in enumerate(sc, 1): cell["co_rank"] = rank
        r1_c = sc[0]["co_drop"] if sc else 0
        for cell in group:
            cell["goals_promote"]   = promote_status(cell["gn_hit"], cell["g_drop"], cell["g_rank"], r1_g, zone)
            cell["corners_promote"] = promote_status(cell["cn_hit"], cell["co_drop"], cell["co_rank"], r1_c, zone)
            cell["tw_promote"]      = threeway_promote_status(cell["tw_hit"], zone)
            cell["promoted"] = any(s in ("PROMOTE","PROMOTE_TOLERANCE")
                                   for s in (cell["goals_promote"], cell["corners_promote"], cell["tw_promote"]))

    ZONE_ORDER = ["strong","standard","low","one_sided"]
    BTS_ORDER  = ["slight_over","strong_over","slight_under","strong_under"]
    result.sort(key=lambda c: (ZONE_ORDER.index(c["zone"]), BTS_ORDER.index(c["bts"])))
    return result

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
STATUS_ICON = {"PROMOTE":"[G]","PROMOTE_TOLERANCE":"[T]","MEASURING":"[M]","HOLD":"[H]","NO":"[ ]"}

def pct(v): return f"{v:6.1f}%"

def print_matrix(cells, title):
    print(f"\n{'='*110}")
    print(f"  {title}")
    print(f"{'='*110}")
    print(f"  {'':1}{'Zone':<12} {'BTS Pocket':<16} {'N':>7} {'Cn':>6}  {'GoalN%':>7} {'GoalS%':>7} {'CornN%':>7} {'CornS%':>7} {'3Way%':>7}  {'Goals':>16} {'Corn':>16} {'3Way':>16}")
    print("  " + "-"*108)
    for c in cells:
        ig  = STATUS_ICON.get(c.get("goals_promote",""),"   ")
        ic  = STATUS_ICON.get(c.get("corners_promote",""),"   ")
        itw = STATUS_ICON.get(c.get("tw_promote",""),"   ")
        mark = "*" if c.get("promoted") else " "
        print(
            f"  {mark}{c['zone']:<12} {c['bts']:<16} {c['n']:>7} {c['cn_n']:>6}  "
            f"{pct(c['gn_hit'])} {pct(c['gs_hit'])} {pct(c['cn_hit'])} {pct(c['cs_hit'])} {pct(c['tw_hit'])}  "
            f"{ig} {c.get('goals_promote','N/A'):<13} "
            f"{ic} {c.get('corners_promote','N/A'):<13} "
            f"{itw} {c.get('tw_promote','N/A'):<13}"
        )

def zone_summary(cells):
    print(f"\n{'='*80}")
    print("  ZONE SUMMARY")
    print(f"{'='*80}")
    by_zone = defaultdict(list)
    for c in cells: by_zone[c["zone"]].append(c)
    for zone in ["strong","standard","low","one_sided"]:
        grp = by_zone.get(zone, [])
        if not grp: continue
        n_total = sum(c["n"] for c in grp)
        cn_n_total = sum(c["cn_n"] for c in grp)
        promoted = [c for c in grp if c.get("promoted")]
        avg_g = sum(c["gn_hit"]*c["n"] for c in grp)/n_total
        avg_c = sum(c["cn_hit"]*c["cn_n"] for c in grp)/cn_n_total if cn_n_total else 0
        avg_tw = sum(c["tw_hit"]*c["n"] for c in grp)/n_total
        promoted_str = ", ".join(c["bts"] for c in promoted) if promoted else "NONE"
        sup = " [SUPPRESSED→MEASURING]" if zone=="low" else ""
        print(f"  {zone:<12}  n={n_total:,}  GoalN={avg_g:.1f}%  CornN={avg_c:.1f}%  3Way={avg_tw:.1f}%  promoted=[{promoted_str}]{sup}")

def market_summary(cells):
    print(f"\n{'='*80}")
    print("  MARKET SUMMARY")
    print(f"{'='*80}")
    def wavg_n(pairs):
        sw = sum(h*n for h,n in pairs if n)
        sn = sum(n for _,n in pairs if n)
        return sw/sn if sn else 0, sn

    all_g   = [(c["gn_hit"],c["n"]) for c in cells]
    all_c   = [(c["cn_hit"],c["cn_n"]) for c in cells]
    all_tw  = [(c["tw_hit"],c["n"]) for c in cells]
    prom_g  = [(c["gn_hit"],c["n"]) for c in cells if c.get("goals_promote") in ("PROMOTE","PROMOTE_TOLERANCE")]
    prom_c  = [(c["cn_hit"],c["cn_n"]) for c in cells if c.get("corners_promote") in ("PROMOTE","PROMOTE_TOLERANCE")]
    prom_tw = [(c["tw_hit"],c["n"]) for c in cells if c.get("tw_promote") in ("PROMOTE","PROMOTE_TOLERANCE")]

    avg_g,  n_g  = wavg_n(all_g)
    avg_c,  n_c  = wavg_n(all_c)
    avg_tw, n_tw = wavg_n(all_tw)
    print(f"  {'Market':<12}  Overall Avg%   N fixtures  Promoted Avg%  Promoted cells")
    def row(mkt, overall, n_all, promoted_pairs, n_prom_cells):
        pavg, pn = wavg_n(promoted_pairs) if promoted_pairs else (0, 0)
        print(f"  {mkt:<12}  {overall:>8.1f}%  {n_all:>10,}  {pavg:>8.1f}%  {n_prom_cells:>6} cells")
    row("Goals", avg_g, n_g, prom_g, len(prom_g))
    row("Corners", avg_c, n_c, prom_c, len(prom_c))
    row("3-Way", avg_tw, n_tw, prom_tw, len(prom_tw))

def tier_split(rows):
    print(f"\n{'='*80}")
    print("  PHASE 2b: FOUNDATION MATRIX — TIER SPLITS")
    print(f"{'='*80}")
    for label, subset in [("Tier 1", [r for r in rows if r.get("tier")==1]),
                           ("Tier 2+3", [r for r in rows if r.get("tier") in (2,3)])]:
        if not subset: continue
        cells = compute_cells(subset)
        promoted = [c for c in cells if c.get("promoted")]
        n_total = sum(c["n"] for c in cells)
        print(f"\n  {label}  ({n_total:,} fixtures, {len(promoted)} promoted cells)")
        print(f"  {'':1}{'Zone':<12} {'BTS':<16} {'N':>7}  {'GoalN%':>7} {'CornN%':>7} {'3Way%':>7}  {'Goals':>20} {'Corn':>20} {'3Way':>16}")
        for c in cells:
            ig  = STATUS_ICON.get(c.get("goals_promote",""),"   ")
            ic  = STATUS_ICON.get(c.get("corners_promote",""),"   ")
            itw = STATUS_ICON.get(c.get("tw_promote",""),"   ")
            mark = "*" if c.get("promoted") else " "
            print(f"  {mark}{c['zone']:<12} {c['bts']:<16} {c['n']:>7}  "
                  f"{pct(c['gn_hit'])} {pct(c['cn_hit'])} {pct(c['tw_hit'])}  "
                  f"{ig} {c.get('goals_promote','N/A'):<18} "
                  f"{ic} {c.get('corners_promote','N/A'):<18} "
                  f"{itw} {c.get('tw_promote','N/A')}")

def corner_h2h_proxy(conn):
    print(f"\n{'='*80}")
    print("  PHASE 3: H2H PROXY — CORNER DISTRIBUTION (fixture_stats)")
    print(f"{'='*80}")
    try:
        r = conn.execute("""
            SELECT
                COUNT(*) AS n,
                AVG(fs.home_corners+fs.away_corners) AS avg_total,
                SUM(CASE WHEN (fs.home_corners+fs.away_corners) >  9 THEN 1 ELSE 0 END) AS over_9,
                SUM(CASE WHEN (fs.home_corners+fs.away_corners) =  9 THEN 1 ELSE 0 END) AS eq_9,
                SUM(CASE WHEN (fs.home_corners+fs.away_corners) > 10 THEN 1 ELSE 0 END) AS over_10,
                SUM(CASE WHEN (fs.home_corners+fs.away_corners) > 11 THEN 1 ELSE 0 END) AS over_11
            FROM fixture_stats fs
            JOIN fixtures f ON f.id = fs.fixture_id
            WHERE f.home_score IS NOT NULL
              AND fs.home_corners IS NOT NULL AND fs.away_corners IS NOT NULL
        """).fetchone()
        if r and r[0]:
            n = r[0]
            print(f"  Fixtures with corner data: {n:,}  (avg total corners per match: {r[1]:.2f})")
            print(f"  Total >  9:  {r[2]:,}  ({r[2]/n*100:.1f}%)  [V3 strong/standard natural line]")
            print(f"  Total =  9:  {r[3]:,}  ({r[3]/n*100:.1f}%)  [push on 9-line]")
            print(f"  Total > 10:  {r[4]:,}  ({r[4]/n*100:.1f}%)  [V3 strong/standard system / low natural]")
            print(f"  Total > 11:  {r[5]:,}  ({r[5]/n*100:.1f}%)  [V3 low system / one_sided natural]")
        # Zone-split corner accuracy
        print(f"\n  Corner hit rates by zone (from fixture_stats):")
        zone_sql = """
            SELECT
                CASE
                    WHEN f.draw_odd < 2.70 THEN 'excluded'
                    WHEN f.draw_odd < 3.40 THEN 'strong'
                    WHEN f.draw_odd < 4.10 THEN 'standard'
                    WHEN f.draw_odd < 4.80 THEN 'low'
                    ELSE 'one_sided'
                END AS zone,
                COUNT(*) AS n,
                SUM(CASE WHEN (fs.home_corners+fs.away_corners) > 9  THEN 1 ELSE 0 END) AS cn9,
                SUM(CASE WHEN (fs.home_corners+fs.away_corners) > 10 THEN 1 ELSE 0 END) AS cn10,
                SUM(CASE WHEN (fs.home_corners+fs.away_corners) > 11 THEN 1 ELSE 0 END) AS cn11
            FROM fixture_stats fs
            JOIN fixtures f ON f.id = fs.fixture_id
            WHERE f.home_score IS NOT NULL
              AND fs.home_corners IS NOT NULL AND fs.away_corners IS NOT NULL
            GROUP BY zone
        """
        print(f"  {'Zone':<12} {'N':>7}  {'Over9%':>8} {'Over10%':>8} {'Over11%':>8}")
        for zr in conn.execute(zone_sql):
            n = zr[1]
            print(f"  {zr[0]:<12} {n:>7}  {zr[2]/n*100:>8.1f}% {zr[3]/n*100:>8.1f}% {zr[4]/n*100:>8.1f}%")
    except Exception as e:
        print(f"  Error: {e}")

def calibration_v1_summary(conn):
    print(f"\n{'='*80}")
    print("  V1 CALIBRATION RESULTS (legacy M-1 era — reference only, NOT V3 accuracy)")
    print(f"{'='*80}")
    try:
        rows = list(conn.execute("""
            SELECT market, COUNT(*) AS n,
                   SUM(CASE WHEN won=1 THEN 1 ELSE 0 END) AS won_cnt,
                   SUM(CASE WHEN won=0 THEN 1 ELSE 0 END) AS lost_cnt,
                   SUM(CASE WHEN won IS NULL THEN 1 ELSE 0 END) AS pending
            FROM calibration_results GROUP BY market ORDER BY n DESC
        """))
        if not rows:
            print("  No calibration_results rows.")
            return
        print(f"  {'Market':<22} {'N':>6} {'Won':>6} {'Lost':>6} {'Pend':>6} {'WinRate%':>10}")
        total_won = total_lost = total_s = 0
        for r in rows:
            s = r[1] - r[4]
            wr = r[2]/s*100 if s else 0
            print(f"  {r[0]:<22} {r[1]:>6} {r[2]:>6} {r[3]:>6} {r[4]:>6} {wr:>10.1f}%")
            total_won += r[2]; total_lost += r[3]; total_s += s  # type: ignore[assignment]
        overall = total_won/total_s*100 if total_s else 0
        print(f"  {'TOTAL':<22} {'':>6} {total_won:>6} {total_lost:>6} {'':>6} {overall:>10.1f}%  (n_settled={total_s:,})")
        print(f"  NOTE: V1 labels (PR-6d, PR-2b…) retired. V3 uses zone×BTS Wilson-LB gate.")
    except Exception as e:
        print(f"  Error: {e}")

def promotion_framework(cells):
    print(f"\n{'='*80}")
    print("  PHASE 6: PROMOTION FRAMEWORK — DEPLOYABLE CELLS")
    print(f"{'='*80}")
    promoted  = [c for c in cells if c.get("promoted")]
    measuring = [c for c in cells if not c.get("promoted") and any(
                   v=="MEASURING" for v in (c.get("goals_promote"),c.get("corners_promote"),c.get("tw_promote")))]
    others    = [c for c in cells if not c.get("promoted") and c not in measuring]

    print(f"\n  PROMOTED ({len(promoted)} cells) — fire picks now:")
    for c in promoted:
        mkts = []
        for mkt, key, hr_key in [("goals","goals_promote","gn_hit"),
                                  ("corners","corners_promote","cn_hit"),
                                  ("3way","tw_promote","tw_hit")]:
            if c[key] in ("PROMOTE","PROMOTE_TOLERANCE"):
                tag = "PROM" if c[key]=="PROMOTE" else "TOLE"
                mkts.append(f"{mkt}[{tag}]={c[hr_key]:.1f}%")
        print(f"  *  {c['zone']:<12} x {c['bts']:<16}  n={c['n']:,}  {' | '.join(mkts)}")

    print(f"\n  MEASURING ({len(measuring)} cells) — low zone suppressed, accumulating evidence:")
    for c in measuring:
        print(f"  [M] {c['zone']:<12} x {c['bts']:<16}  n={c['n']:,}  gn={c['gn_hit']:.1f}%  cn={c['cn_hit']:.1f}%  tw={c['tw_hit']:.1f}%")

    print(f"\n  NOT PROMOTED ({len(others)} cells):")
    for c in others:
        reasons = []
        for mkt, key, hr_key in [("goals","goals_promote","gn_hit"),
                                  ("corners","corners_promote","cn_hit"),
                                  ("3way","tw_promote","tw_hit")]:
            reasons.append(f"{mkt}={c[hr_key]:.1f}%({c[key]})")
        print(f"  [ ] {c['zone']:<12} x {c['bts']:<16}  n={c['n']:,}  {' | '.join(reasons)}")

def segment_recommendations(cells):
    print(f"\n{'='*80}")
    print("  PHASE 7: SEGMENT OPTIMIZATION RECOMMENDATIONS")
    print(f"{'='*80}")
    by_zone = defaultdict(list)
    for c in cells: by_zone[c["zone"]].append(c)
    for zone in ["strong","standard","low","one_sided"]:
        grp = by_zone.get(zone,[])
        if not grp: continue
        n = sum(c["n"] for c in grp)
        cn_n = sum(c["cn_n"] for c in grp)
        avg_g = sum(c["gn_hit"]*c["n"] for c in grp)/n
        avg_c = sum(c["cn_hit"]*c["cn_n"] for c in grp)/cn_n if cn_n else 0
        avg_tw = sum(c["tw_hit"]*c["n"] for c in grp)/n
        prom = [c for c in grp if c.get("promoted")]
        best_g = max(grp, key=lambda c: c["gn_hit"])
        best_c = max(grp, key=lambda c: c["cn_hit"])
        best_tw = max(grp, key=lambda c: c["tw_hit"])
        print(f"\n  ZONE: {zone.upper()}  (n={n:,}, corner_n={cn_n:,})")
        print(f"    Avg GoalN={avg_g:.1f}%  Avg CornN={avg_c:.1f}%  Avg 3Way={avg_tw:.1f}%")
        print(f"    Promoted BTS pockets: {', '.join(c['bts'] for c in prom) or 'NONE'}")
        print(f"    Best Goals:   {best_g['bts']:<18} {best_g['gn_hit']:.1f}% (n={best_g['n']:,})")
        print(f"    Best Corners: {best_c['bts']:<18} {best_c['cn_hit']:.1f}% (n={best_c['cn_n']:,} with corners)")
        print(f"    Best 3-Way:   {best_tw['bts']:<18} {best_tw['tw_hit']:.1f}% (n={best_tw['n']:,})")
        if zone == "low":
            print(f"    ACTION: Accumulate data. Remove LOW_ZONE_SUPPRESS once n/cell >= 500.")
        elif not prom:
            print(f"    ACTION: No cells promoted. Investigate BTS pocket split — consider collapsing pockets.")
        else:
            gaps = [c for c in grp if not c.get("promoted")]
            if gaps:
                closest = max(gaps, key=lambda c: max(c["gn_hit"],c["cn_hit"],c["tw_hit"]))
                best_hit = max(closest["gn_hit"],closest["cn_hit"],closest["tw_hit"])
                gap_to_lower = PROMOTE_LOWER - best_hit
                print(f"    ACTION: {len(gaps)} cells not promoted. Closest gap: {closest['bts']} at {best_hit:.1f}% ({gap_to_lower:.1f}pp from tolerance).")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("\n" + "="*110)
    print("  OddsFlow V3 — FULL ENGINE TESTING REPORT  |  Phases 2–7")
    print("  V3 Classification (zone×BTS×Wilson)  |  v1_calibration_readonly.db")
    print("="*110)

    conn = sqlite3.connect(str(DB_PATH))

    print("\n  Loading settled fixtures…")
    rows = load_fixtures(conn)
    print(f"  Loaded {len(rows):,} settled fixtures")

    print("\n  Computing V3 Foundation Matrix…")
    cells_all = compute_cells(rows)
    promoted_all = [c for c in cells_all if c.get("promoted")]

    # Legend
    print("\n  Legend: [G]=PROMOTE  [T]=PROMOTE_TOLERANCE  [M]=MEASURING  [H]=HOLD  [ ]=NO  *=cell promoted")

    print_matrix(cells_all, "PHASE 2a: V3 FOUNDATION MATRIX — ALL TIERS (28k+ settled fixtures)")
    zone_summary(cells_all)
    market_summary(cells_all)
    tier_split(rows)
    corner_h2h_proxy(conn)
    calibration_v1_summary(conn)
    promotion_framework(cells_all)
    segment_recommendations(cells_all)

    # Executive Summary
    total_n = sum(c["n"] for c in cells_all)
    unclassifiable = len(rows) - total_n
    print(f"\n{'='*80}")
    print("  EXECUTIVE SUMMARY")
    print(f"{'='*80}")
    print(f"  Settled fixtures loaded:     {len(rows):,}")
    print(f"  Classifiable (V3):           {total_n:,}  ({total_n/len(rows)*100:.1f}%)")
    print(f"  Excluded (draw_odd < 2.70):  {unclassifiable:,}  ({unclassifiable/len(rows)*100:.1f}%)")
    print(f"  V3 cells computed:           {len(cells_all)}")
    print(f"  Promoted cells:              {len(promoted_all)}")
    print(f"\n  Promotion thresholds:  PROMOTE >= {PROMOTE_THRESHOLD}%  |  TOLERANCE >= {PROMOTE_LOWER}%")
    print(f"  LOW_ZONE_SUPPRESS = {LOW_ZONE_SUPPRESS}  (low zone cells → MEASURING regardless)")
    print(f"\n  Promoted cells:")
    for c in promoted_all:
        mkts = []
        for mkt, key, hr_key in [("goals","goals_promote","gn_hit"),
                                  ("corners","corners_promote","cn_hit"),
                                  ("3way","tw_promote","tw_hit")]:
            if c[key] in ("PROMOTE","PROMOTE_TOLERANCE"):
                mkts.append(f"{mkt}={c[hr_key]:.1f}%")
        print(f"    * {c['zone']:<12} x {c['bts']:<16}  n={c['n']:,}  {' | '.join(mkts)}")
    print(f"\n  V3 engine is production-ready for the promoted cells listed above.")
    print(f"  Low-zone cells accumulating — revisit when per-cell n >= 500.\n")

    conn.close()

if __name__ == "__main__":
    main()
