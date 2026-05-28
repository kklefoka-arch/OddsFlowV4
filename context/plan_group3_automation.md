# Group 3 Plan — Automation
## Gaps: G5 (manual settle), G6 (no cron/scheduler)

**Phase connection:** Phase 8 (Score Update) → Phase 9 (Settle) → Phase 1 (Fetch, daily)
**Status:** IMPLEMENTED in Sessions 6 + 13 + 15 + 18. `run_daily.ps1` exists (4-step chain incl. emit_picks). `setup_scheduler.ps1` registers 12 Task Scheduler jobs (Europe + SA + Dawn SA windows + refresh_odds + refresh_stats + server + ngrok). All daily scripts write `system_health` heartbeats. Retained as audit trail.
**Dependency:** Group 1 livescores path is implemented; the additional Task Scheduler jobs remain to cover non-livescores windows.

---

## Scope note

If Group 1 (Display layer) implements the livescores auto-trigger hook:
- Match finish detected by livescores polling → score written inline → settle triggered inline
- **G5 is closed by Group 1 for match-day fixtures**
- Group 3 scope reduces to: scheduling fetch_upcoming.py daily only

If Group 1 does NOT implement the auto-trigger hook:
- G5 remains open — settle.py must be triggered after each match day
- Group 3 must cover: fetch_upcoming.py daily + fetch_results.py post-match + settle.py post-results

**This plan covers both scenarios.** Implement the correct path after Group 1 scope is confirmed.

---

## G5 — Manual Settle Trigger

### Scenario A: Group 1 livescores hook implemented
G5 is closed. No action required in Group 3.

### Scenario B: Group 1 livescores hook NOT implemented

**Approach: Chained daily script**

Create `run_daily.bat` (or `run_daily.ps1`) that runs the full daily operator flow in sequence:

```powershell
# run_daily.ps1
Set-Location C:\OddsFlowV4

Write-Host "=== fetch_upcoming ===" 
python fetch_upcoming.py

Write-Host "=== fetch_results ==="
python fetch_results.py

Write-Host "=== settle ==="
python settle.py

Write-Host "=== done ==="
```

This script is the operator's single command. It can also be the target of Windows Task Scheduler (G6).

---

## G6 — Scheduler

**Platform:** Windows — use Windows Task Scheduler (built-in, no additional dependencies)

### Scenario A: Group 1 livescores hook implemented

Only fetch_upcoming.py needs scheduling (livescores handles match-day automation).

**Task: daily_fetch**
- Trigger: daily at 09:00 UTC (adjust to match Sportmonks update cadence)
- Action: `python C:\OddsFlowV4\fetch_upcoming.py`
- Working dir: `C:\OddsFlowV4`
- Log: `C:\OddsFlowV4\logs\fetch_upcoming.log` (append)

### Scenario B: Group 1 livescores hook NOT implemented

Three tasks:

**Task 1: daily_fetch** (same as above)

**Task 2: post_match_results**
- Trigger: daily at 23:30 UTC (after most European match windows close)
- Action: `python C:\OddsFlowV4\fetch_results.py`
- Or: use `run_daily.ps1` which chains all three scripts

**Task 3: daily_settle** (if not chained)
- Trigger: daily at 23:45 UTC (after fetch_results)
- Action: `python C:\OddsFlowV4\settle.py`

### Logging
All scripts should append stdout to `logs/` so Task Scheduler runs are auditable:

```powershell
python fetch_upcoming.py >> C:\OddsFlowV4\logs\fetch_upcoming.log 2>&1
```

Create `logs/` directory. Add `logs/*.log` to `.gitignore`.

### system_health table
The DB has a `system_health` table (currently never written). Each script run should write a heartbeat:
```sql
INSERT OR REPLACE INTO system_health (script, last_run, status)
VALUES ('fetch_upcoming', datetime('now'), 'ok');
```
This lets the Reports tab surface "last run" times and detect stale fetches.

---

## Files to create/modify

| File | Change |
|------|--------|
| `run_daily.ps1` | New — chained operator script (Scenario B) |
| `fetch_upcoming.py` | Add system_health heartbeat write |
| `fetch_results.py` | Add system_health heartbeat write |
| `settle.py` | Add system_health heartbeat write |
| `logs/` | New directory (gitignored) |
| `.gitignore` | Add `logs/*.log` |
| `setup_scheduler.ps1` | New — creates Windows Task Scheduler tasks (operator runs once) |

---

## Implementation order within group

1. Confirm Group 1 scope (livescores hook yes/no)
2. Add system_health heartbeat to all three scripts
3. Create `logs/` + `.gitignore` entry
4. If Scenario B: create `run_daily.ps1`
5. Create `setup_scheduler.ps1` — run once to register tasks
6. Verify: run Task Scheduler task manually, check log output, check system_health table

---

## Cross-cut summary across all groups

| Group 1 decision | Group 3 impact |
|-----------------|---------------|
| Livescores hook implemented | G5 closed; G6 = 1 scheduled task only |
| Livescores hook deferred | G5 open; G6 = 3 scheduled tasks + run_daily.ps1 |

**Recommendation:** Implement Group 1 with the livescores hook. It is more complex but collapses Group 3 into a single scheduled task and eliminates the manual post-match workflow entirely. Worth the extra build effort in Group 1.
