# OddsFlow V4 -- Windows Task Scheduler setup
# Run ONCE as Administrator to register scheduled tasks.
#
# Tasks registered:
#   OddsFlow_FetchUpcoming       -- daily 08:00 SAST (06:00 UTC) -- morning fixture + odds refresh
#   OddsFlow_EmitPicks           -- daily 08:05 SAST             -- emit picks after odds refresh
#   OddsFlow_RefreshOdds         -- daily 14:30 SAST             -- intraday odds refresh for evening matches (M2)
#   OddsFlow_FetchResults        -- daily 23:30 SAST (21:30 UTC) -- European match window close
#   OddsFlow_Settle              -- daily 23:45 SAST (21:45 UTC) -- settle after European results
#   OddsFlow_RefreshStats        -- daily 00:00 SAST             -- backfill corner stats for fixtures missing them
#   OddsFlow_FetchResults_SA     -- daily 03:00 SAST (01:00 UTC) -- South American night matches
#   OddsFlow_Settle_SA           -- daily 03:15 SAST (01:15 UTC) -- settle after SA results
#   OddsFlow_FetchResults_DawnSA -- daily 06:00 SAST (04:00 UTC) -- catches late SA matches the 03:00 pass missed (M3)
#   OddsFlow_Settle_DawnSA       -- daily 06:15 SAST (04:15 UTC) -- settle after the dawn SA pass
#   OddsFlow_Ngrok               -- at system startup            -- keep ngrok tunnel alive
#   OddsFlow_Server              -- at system startup            -- uvicorn (port 8083)
#
# Why two fetch_results runs:
#   fetch_results uses  date < UTC_today  as eligibility.
#   South American fixtures kick off 00:00-02:00 UTC -- still "today" UTC at 21:30 UTC.
#   The 03:00 SAST run (01:00 UTC) catches those as "yesterday" and settles them.
#
# Verify after running: taskschd.msc -> Task Scheduler Library -> OddsFlow_*

$python  = (Get-Command python).Source
$workdir = "C:\OddsFlowV4"
$logdir  = "C:\OddsFlowV4\logs"

if (-not (Test-Path $logdir)) { New-Item -ItemType Directory -Path $logdir | Out-Null }

function Register-OddsFlowTask {
    param($name, $script, $hour, $minute)
    $action    = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory $workdir
    $trigger   = New-ScheduledTaskTrigger -Daily -At "$($hour):$($minute)"
    $settings  = New-ScheduledTaskSettingsSet `
                    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
                    -StartWhenAvailable
    # S4U principal so Start-ScheduledTask works from any context (incl. WSL).
    # Interactive LogonType queues the task until an interactive shell exists.
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                                              -LogonType S4U -RunLevel Highest
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
                           -Settings $settings -Principal $principal -Force
    Write-Host "Registered: $name  ($($hour):$([string]$minute.ToString('D2')) local)" -ForegroundColor Green
}

# European window
Register-OddsFlowTask "OddsFlow_FetchUpcoming"   "fetch_upcoming.py"  8  0
Register-OddsFlowTask "OddsFlow_EmitPicks"       "emit_picks.py"      8  5
Register-OddsFlowTask "OddsFlow_RefreshOdds"     "refresh_odds.py"   14 30
Register-OddsFlowTask "OddsFlow_FetchResults"    "fetch_results.py"   23 30
Register-OddsFlowTask "OddsFlow_Settle"          "settle.py"          23 45

# Nightly corner-stats backfill (V3.1 — catches Sportmonks late-arriving corner data)
Register-OddsFlowTask "OddsFlow_RefreshStats"    "refresh_stats.py"   0  0

# South American window (runs in the early hours -- catches previous UTC-day SA matches)
Register-OddsFlowTask "OddsFlow_FetchResults_SA" "fetch_results.py"   3  0
Register-OddsFlowTask "OddsFlow_Settle_SA"       "settle.py"          3  15

# Dawn SA pass (M3 — catches SA matches kicking off 01:30-02:00 UTC that the
# 03:00 SAST / 01:00 UTC pass found still in-play, by re-checking at 04:00 UTC)
Register-OddsFlowTask "OddsFlow_FetchResults_DawnSA" "fetch_results.py"  6  0
Register-OddsFlowTask "OddsFlow_Settle_DawnSA"       "settle.py"          6 15

# Nightly orphan reconciler (Session 23d Bundle 4)
# Marks picks that cannot be settled (dropped league, or stale > 48h) as
# outcome='ORPHAN' so they leave the "pending" count. Runs after the dawn
# SA settle pass so it sees a fully-up-to-date settlement view.
Register-OddsFlowTask "OddsFlow_ReconcileOrphans" "scripts/reconcile_orphans.py" 6 30

# Livescores poller (Session 23d follow-up — replaces "Sportmonks webhook")
# Sportmonks v3 does not document a public webhook subscription flow. The
# documented real-time path is polling the livescores endpoint. This task
# runs scripts/livescores_poller.py every 5 minutes, which calls the local
# /api/livescores endpoint, auto-writes scores for finished fixtures, and
# settles pending picks via the existing _write_and_settle() helper.
# Effective settlement latency drops from ~8h worst case to ~5 min.
$lsAction    = New-ScheduledTaskAction -Execute $python `
                  -Argument "scripts/livescores_poller.py" `
                  -WorkingDirectory $workdir
$lsTrigger   = New-ScheduledTaskTrigger -Once -At (Get-Date) `
                  -RepetitionInterval (New-TimeSpan -Minutes 5) `
                  -RepetitionDuration (New-TimeSpan -Days 3650)
$lsSettings  = New-ScheduledTaskSettingsSet `
                  -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
                  -MultipleInstances IgnoreNew `
                  -StartWhenAvailable
$lsPrincipal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                                            -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName "OddsFlow_LivescoresPoller" -Action $lsAction `
                       -Trigger $lsTrigger -Settings $lsSettings `
                       -Principal $lsPrincipal -Force
Write-Host "Registered: OddsFlow_LivescoresPoller  (every 5 min, MultipleInstances=IgnoreNew)" -ForegroundColor Green

# Weekly DB maintenance (Session 23d Bundle 6)
# PRAGMA optimize + ANALYZE + conditional VACUUM with dated backup.
# Sundays 02:00 SAST — between Settle (Sat 23:45) and the SA fetch (Sun 03:00)
# so nothing else is writing during the VACUUM. Uses a weekly trigger rather
# than the daily helper above.
$dbmaintAction    = New-ScheduledTaskAction -Execute $python `
                       -Argument "scripts/db_maintenance.py" `
                       -WorkingDirectory $workdir
$dbmaintTrigger   = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "02:00"
$dbmaintSettings  = New-ScheduledTaskSettingsSet `
                       -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
                       -StartWhenAvailable
$dbmaintPrincipal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                                                 -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName "OddsFlow_DBMaintenance" -Action $dbmaintAction `
                       -Trigger $dbmaintTrigger -Settings $dbmaintSettings `
                       -Principal $dbmaintPrincipal -Force
Write-Host "Registered: OddsFlow_DBMaintenance  (weekly Sunday 02:00)" -ForegroundColor Green

# Ngrok — startup task, restarts on failure, keeps the tunnel alive
# (PS 5.1 compatible — replaces null-conditional `?.` which is PS 7+ only)
$ngrokCmd = Get-Command ngrok -ErrorAction SilentlyContinue
$ngrok    = if ($ngrokCmd) { $ngrokCmd.Source } else { "ngrok" }
$ngrokAction    = New-ScheduledTaskAction -Execute $ngrok -Argument "http 8083" -WorkingDirectory $workdir
$ngrokTrigger   = New-ScheduledTaskTrigger -AtStartup
$ngrokSettings  = New-ScheduledTaskSettingsSet `
                     -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
                     -RestartCount 10 `
                     -RestartInterval (New-TimeSpan -Minutes 1) `
                     -StartWhenAvailable
$ngrokPrincipal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                                              -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName "OddsFlow_Ngrok" -Action $ngrokAction -Trigger $ngrokTrigger `
                       -Settings $ngrokSettings -Principal $ngrokPrincipal -Force
Write-Host "Registered: OddsFlow_Ngrok  (startup, restarts on failure)" -ForegroundColor Green

# Uvicorn server — startup task, restarts on failure
# emit_picks.py calls http://localhost:8083/picks at 08:05, so the server
# must be running at that time. Without this task, the server doesn't
# auto-start after a reboot and morning emission silently fails.
$uvicornAction    = New-ScheduledTaskAction `
                     -Execute "powershell.exe" `
                     -Argument "-NoProfile -WindowStyle Hidden -Command `"Set-Location C:\OddsFlowV4; uvicorn app.main:app --host 0.0.0.0 --port 8083`"" `
                     -WorkingDirectory $workdir
$uvicornTrigger   = New-ScheduledTaskTrigger -AtStartup
$uvicornSettings  = New-ScheduledTaskSettingsSet `
                     -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
                     -RestartCount 10 `
                     -RestartInterval (New-TimeSpan -Minutes 1) `
                     -StartWhenAvailable
$uvicornPrincipal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                                                -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName "OddsFlow_Server" -Action $uvicornAction -Trigger $uvicornTrigger `
                       -Settings $uvicornSettings -Principal $uvicornPrincipal -Force
Write-Host "Registered: OddsFlow_Server  (startup, restarts on failure)" -ForegroundColor Green

Write-Host ""
Write-Host "All 15 tasks registered." -ForegroundColor Cyan
Write-Host "Verify in Task Scheduler: taskschd.msc -> Task Scheduler Library"
Write-Host ""
Write-Host "Times are LOCAL (SAST = UTC+2). Adjust if your clock differs."
