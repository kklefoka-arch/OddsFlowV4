# OddsFlow V4 — Daily operator run
# Order: fetch_upcoming -> emit_picks -> fetch_results -> settle -> reconcile_orphans
# (Re-emit chain after refresh_odds is registered separately at 14:30 SAST via
#  OddsFlow_RefreshOdds + an inline emit_picks --mode reemit call.)
# Run from C:\OddsFlowV4

Set-Location C:\OddsFlowV4
$logDir = "C:\OddsFlowV4\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$stamp = (Get-Date -Format "yyyy-MM-dd_HH-mm")

Write-Host "=== fetch_upcoming ===" -ForegroundColor Cyan
python fetch_upcoming.py 2>&1 | Tee-Object -FilePath "$logDir\fetch_upcoming_$stamp.log"

Write-Host "`n=== emit picks (morning) ===" -ForegroundColor Cyan
python emit_picks.py --mode emit 2>&1 | Tee-Object -FilePath "$logDir\emit_picks_$stamp.log"

Write-Host "`n=== fetch_results ===" -ForegroundColor Cyan
python fetch_results.py 2>&1 | Tee-Object -FilePath "$logDir\fetch_results_$stamp.log"

Write-Host "`n=== settle ===" -ForegroundColor Cyan
python settle.py 2>&1 | Tee-Object -FilePath "$logDir\settle_$stamp.log"

Write-Host "`n=== reconcile_orphans ===" -ForegroundColor Cyan
python scripts/reconcile_orphans.py 2>&1 | Tee-Object -FilePath "$logDir\reconcile_orphans_$stamp.log"

Write-Host "`n=== heartbeat ===" -ForegroundColor Cyan
python -c "
import sqlite3, datetime
conn = sqlite3.connect(r'C:\OddsFlowV4\data\oddsflow_v4.db')
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
conn.execute('INSERT INTO system_health (metric, value) VALUES (?, ?)', ('cron_heartbeat', f'step=complete ts={now}'))
conn.commit()
conn.close()
print('Heartbeat written.')
"

Write-Host "`n=== done ===" -ForegroundColor Green
