# OddsFlow V4 -- Windows Task Scheduler setup
# Run ONCE as Administrator to register scheduled tasks.
#
# Tasks registered:
#   OddsFlow_FetchUpcoming    -- daily 08:00 SAST (06:00 UTC) -- morning fixture + odds refresh
#   OddsFlow_FetchResults     -- daily 23:30 SAST (21:30 UTC) -- European match window close
#   OddsFlow_Settle           -- daily 23:45 SAST (21:45 UTC) -- settle after European results
#   OddsFlow_FetchResults_SA  -- daily 03:00 SAST (01:00 UTC) -- South American night matches
#   OddsFlow_Settle_SA        -- daily 03:15 SAST (01:15 UTC) -- settle after SA results
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
    $action   = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory $workdir
    $trigger  = New-ScheduledTaskTrigger -Daily -At "$($hour):$($minute)"
    $settings = New-ScheduledTaskSettingsSet `
                    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
                    -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
                           -Settings $settings -RunLevel Highest -Force
    Write-Host "Registered: $name  ($($hour):$([string]$minute.ToString('D2')) local)" -ForegroundColor Green
}

# European window
Register-OddsFlowTask "OddsFlow_FetchUpcoming"   "fetch_upcoming.py"  8  0
Register-OddsFlowTask "OddsFlow_FetchResults"    "fetch_results.py"   23 30
Register-OddsFlowTask "OddsFlow_Settle"          "settle.py"          23 45

# South American window (runs in the early hours -- catches previous UTC-day SA matches)
Register-OddsFlowTask "OddsFlow_FetchResults_SA" "fetch_results.py"   3  0
Register-OddsFlowTask "OddsFlow_Settle_SA"       "settle.py"          3  15

Write-Host ""
Write-Host "All 5 tasks registered." -ForegroundColor Cyan
Write-Host "Verify in Task Scheduler: taskschd.msc -> Task Scheduler Library"
Write-Host ""
Write-Host "Times are LOCAL (SAST = UTC+2). Adjust if your clock differs."
