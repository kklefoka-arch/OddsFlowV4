# OddsFlow V4 — Windows Task Scheduler setup
# Run once as Administrator to register scheduled tasks.
#
# Tasks registered:
#   OddsFlow_FetchUpcoming  — daily at 09:00 UTC (10:00 or 11:00 local depending on DST)
#   OddsFlow_FetchResults   — daily at 23:30 UTC (after European match windows close)
#   OddsFlow_Settle         — daily at 23:45 UTC (after fetch_results)
#
# If Group 1 livescores auto-trigger is active, fetch_results and settle
# are covered during match windows. These tasks catch any fixtures missed.

$python  = (Get-Command python).Source
$workdir = "C:\OddsFlowV4"

function Register-OddsFlowTask {
    param($name, $script, $hour, $minute)
    $action  = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory $workdir
    $trigger = New-ScheduledTaskTrigger -Daily -At "$($hour):$($minute)"
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
                                              -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
                           -Settings $settings -RunLevel Highest -Force
    Write-Host "Registered: $name" -ForegroundColor Green
}

Register-OddsFlowTask "OddsFlow_FetchUpcoming" "fetch_upcoming.py" 9  0
Register-OddsFlowTask "OddsFlow_FetchResults"  "fetch_results.py"  23 30
Register-OddsFlowTask "OddsFlow_Settle"        "settle.py"         23 45

Write-Host "`nAll tasks registered. Verify in Task Scheduler (taskschd.msc)."
Write-Host "Note: times are in local time — adjust if needed to match UTC target."
