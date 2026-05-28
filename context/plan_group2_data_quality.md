# Group 2 Plan — Data Quality
## Gaps: G2 (draw_zone/bts_pocket unwritten), G3 (ghost fixtures)

**Phase connection:** Phase 1 (Fetch/Land) → Phase 3 (Classify)
**Status:** IMPLEMENTED in Session 6 (`migrate_cleanup_ghosts.py`, `migrate_write_zones.py`, `fetch_upcoming.py` writes zone/bts on insert/update). Retained as audit trail.
**Dependency:** None — Group 2 was independent of Groups 1 and 3.

---

## G3 — Ghost Fixture Cleanup

### What this is
1,349 fixtures in the DB with `sportmonks_id IS NULL`. These were seeded from the V2/V3 historical pipeline with no Sportmonks reference. They have no odds, no pick eligibility, and cannot be updated by `fetch_upcoming.py` or `fetch_results.py`.

### Impact of keeping them
- Foundation matrix computation (`load_foundation`) queries `WHERE home_score IS NOT NULL`. Ghosts with scores ARE included in calibration — that is correct behaviour.
- Ghosts WITHOUT scores (`home_score IS NULL AND sportmonks_id IS NULL`) are excluded from picks already (no odds). They do appear in upcoming fixture counts, inflating the "upcoming" number by up to 1,349.
- No picks risk — confirmed. No emit_log entries reference sportmonks_id=NULL fixtures.

### Approach: Targeted delete — NULL sportmonks_id + NULL home_score

```sql
DELETE FROM fixtures
WHERE sportmonks_id IS NULL
  AND home_score IS NULL;
```

This removes only the ghost upcoming rows — fixtures that will never receive odds, scores, or picks. Historical ghosts with scores (sportmonks_id IS NULL but home_score IS NOT NULL) are kept — they contribute to the foundation matrix.

**Script:** `migrate_cleanup_ghosts.py`
- Dry run first: report count before delete
- Confirm count matches expectation (~1,349)
- Execute delete
- Report remaining fixtures count

### Verification
- Before: ~4,391 upcoming (sportmonks_id=NULL upcoming inflates this)
- After: upcoming count drops by actual ghost count
- Foundation matrix fixture count: unchanged (ghosts with scores stay)
- Picks: unchanged

---

## G2 — Write draw_zone / bts_pocket to Fixtures on Insert

### What this is
`fixtures` schema has `draw_zone` and `bts_pocket` columns. Nothing writes them. `classify_fixture()` computes them on-the-fly from odds whenever needed. This means every call to classify a fixture re-derives zone and bts from raw odds.

### Is this worth doing?

**Arguments for:**
- Direct SQL filter on `draw_zone` and `bts_pocket` — enables queries like "all strong/strong_over fixtures" without Python classification
- G4 (similar-odds inspector) would benefit: `WHERE draw_zone=? AND bts_pocket=?` instead of fetching all settled rows and re-classifying in Python
- Drift monitoring queries simplify

**Arguments against:**
- Denormalization — zone and bts are derivable from draw_odd, btts_yes_odd, btts_no_odd
- If zone/bts thresholds change (they have before), stored values become stale
- Current on-the-fly approach is fast enough at 28,607 fixtures

**Decision: Implement — with a backfill migration**

The G4 similar-odds query (Group 1) needs to scan all settled fixtures and classify each one. At 28,607 rows, classifying in Python on every request adds latency. Storing draw_zone/bts_pocket makes that query a simple indexed filter.

### Approach

**Step 1 — Backfill existing rows**
```sql
-- Conceptual (done via Python, not raw SQL, to use classify logic)
-- fetch all settled rows with draw_odd, btts_yes_odd, btts_no_odd
-- call zone_of() + bts_of() per row
-- UPDATE fixtures SET draw_zone=?, bts_pocket=? WHERE id=?
```
Script: `migrate_write_zones.py`

**Step 2 — Write on insert in fetch_upcoming.py**
```python
zone = zone_of(row.get("draw_odd"))
bts  = bts_of(row.get("btts_yes_odd"), row.get("btts_no_odd"))
# add draw_zone=zone, bts_pocket=bts to INSERT and UPDATE statements
```

**Step 3 — Write on score update in fetch_results.py**
- fetch_results.py does not insert fixtures, only updates scores — no change needed

### Cross-cut to G4
Once draw_zone/bts_pocket are stored, `GET /inspector/similar` becomes:
```sql
SELECT * FROM fixtures
WHERE draw_zone = ? AND bts_pocket = ?
  AND home_score IS NOT NULL
ORDER BY date DESC LIMIT 50
```
Instead of fetching all settled rows and classifying in Python. This is the primary payoff.

### Files to create/modify
| File | Change |
|------|--------|
| `migrate_cleanup_ghosts.py` | New — dry-run + delete ghost fixtures |
| `migrate_write_zones.py` | New — backfill draw_zone/bts_pocket on all classifiable rows |
| `fetch_upcoming.py` | Add draw_zone + bts_pocket to INSERT and UPDATE |

---

## Implementation order within group

1. `migrate_cleanup_ghosts.py` — dry run, verify count, execute (fast, safe, no logic risk)
2. `migrate_write_zones.py` — backfill draw_zone/bts_pocket on existing settled + upcoming rows
3. `fetch_upcoming.py` — add zone/bts writes on insert and update
4. Verify: `SELECT draw_zone, count(*) FROM fixtures GROUP BY draw_zone` shows expected distribution

Run Group 2 after Group 1 is implemented, so G4's similar-odds query can use the stored columns immediately.
