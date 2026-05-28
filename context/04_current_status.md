# Current Status — OddsFlow V4

Update this file at the end of every session.
Last updated: 2026-05-28 (Session 19 — V3 restoration + raw-notes zone overlay)

---

## State: Running ✅ — V3 restored

| Item | Detail |
|------|--------|
| Folder | `C:\OddsFlowV4` |
| Port | 8083 (local) |
| ngrok | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v4.db` |
| GitHub | `github.com/kklefoka-arch/OddsFlowV4` |
| Active policy | **V3** (Session 11 baseline) — `static_policy.V3_ACTIVE`, 9 cells, 2-key (zone × bts) |
| Zone boundaries | strong 2.90–3.30, standard 3.30–3.80, low 3.80–4.30, one_sided ≥4.30 (Session 19 raw-notes overlay) |
| Fixtures | 51,057 total — 46,905 settled, 4,152 upcoming. draw_zone re-backfilled (8,145 updates). |
| Fixture stats | 38,574 |
| Distribution post-overlay | strong 7,789 / standard 13,140 / low 3,982 / one_sided 3,840 / excluded 22,306 |
| emit_log | 613 rows (pre-restore). New emits will write under the V3 partition; existing rows keep their stored zone for historical fidelity. |
| pick_results | 275 — 156W / 76L / 43V (non-loss 73.5% over the 7d window prior to restore) |
| Leagues | 62 in DB (30 subscribed) |
| DB backup before restore | `data/oddsflow_v4.db.bak.2026-05-28-session19` |

## How to start

Server runs from Task Scheduler (`OddsFlow_Server`). Manual fallback:

```powershell
Set-Location C:\OddsFlowV4
uvicorn app.main:app --host 0.0.0.0 --port 8083
```

## Daily flow (chained in `run_daily.ps1`)

```powershell
python fetch_upcoming.py    # refresh odds + kickoff datetimes
python emit_picks.py        # call /picks?days=3 -> emit_log
python fetch_results.py     # write scores + fixture_stats
python settle.py            # write pick_results
```

12 scheduler jobs handle this automatically — see CLAUDE.md → Scheduler.

---

## Known issues / observations

| # | Item | Notes |
|---|------|-------|
| 1 | `static_policy.V3_MARKETS` hit rates are pre-overlay | Historical baselines (e.g., low:slight_over 84.9% n=1733) were computed against the old 4.10–4.80 low range. Treat as reference; the next 6 weeks of settlement will yield the new baseline. Don't gate emission on these numbers. |
| 2 | Old emit_log rows keep their pre-overlay `zone` value | Historical record — intentional. New emits use the new boundaries. Inspector/reports may show a small zone-boundary discontinuity around the restore date; expected. |
| 3 | `pick_odd` NULL on 100% of corners_nl and ~95% of goals_nl rows | By design — natural-line-only policy (Over 1.5 Goals / Over 8.5 Corners rarely quoted by Sportmonks). SPA renders `—`. Future EV layer (Project 3) is gated on the 6-week validation. |
| 4 | 96% of upcoming fixtures have no `draw_zone` | Not a bug — most upcoming fixtures don't yet carry a quoted `draw_odd`. Within the 7-day window, ~41% carry odds and classify. |
| 5 | `LOW_ZONE_SUPPRESS` differs between modules | `static_policy.py = False` (pick firing — low zone active). `promotion.py = True` (foundation matrix display — low cells shown as `MEASURING`). Intentional split. |
| 6 | `pick_results.outcome` stores string `WIN`/`LOSS`/`VOID` | Float lives in `actual_value`. Filter on `outcome='WIN'` or use `actual_value` — never numeric compare against `outcome`. |
| 7 | `df_level` columns on fixtures + emit_log are inert | Retained from V3.1 schema (additive). New writes are NULL. Will be dropped only if Durable Rule 1 ever relaxes. |

---

## Session log

| Session | Date | Work done |
|---------|------|-----------|
| 1–8 | 2026-05-22 → 2026-05-24 | V4 built, SPA + 7 tabs, league fixes, classification + matrix wired |
| 9 | 2026-05-25 | 8-group fix plan, supersede logic, monthly fetch windows |
| 10 | 2026-05-25 | V3 policy deployed (9 cells, 4 markets) |
| 11 | 2026-05-26 | First V3 settlement (22W 8L 6V); plain-language summary screenshot captured |
| 12 | 2026-05-26 | Project 2 calibration completed — declared **reference-only, not a gate** |
| 13 | 2026-05-26 | 5 scheduler tasks activated |
| 14 | 2026-05-26 | League migration analysis (Americas/Asia) |
| 15 | 2026-05-27 | Process audit M1/M2/M3 — corners settlement, refresh_odds, dawn SA catch-up |
| 16 | 2026-05-27 | **Engine reverted to literal Session 11 reference** (first revert) |
| 17 | 2026-05-27 | Enhanced analysis built from raw-notes spec — DF separation evidence, 6-pocket BTS |
| 18 | 2026-05-27 | V3.1 DF-aware partition deployed (20 cells) — *the drift this session reversed* |
| 19 | 2026-05-28 | **Second V3 restoration + raw-notes zone-boundary overlay**. DF removed everywhere. Boundaries 2.90/3.30/3.80/4.30. 8,145 draw_zone rows re-backfilled. Durable Rules pinned in CLAUDE.md to prevent re-drift. AI Website docs aligned. |
