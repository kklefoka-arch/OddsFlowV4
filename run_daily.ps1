# OddsFlow V4 — Daily operator run
# Order: fetch_upcoming -> fetch_results -> settle
# Run from C:\OddsFlowV4

Set-Location C:\OddsFlowV4
$logDir = "C:\OddsFlowV4\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$stamp = (Get-Date -Format "yyyy-MM-dd_HH-mm")

Write-Host "=== fetch_upcoming ===" -ForegroundColor Cyan
python fetch_upcoming.py 2>&1 | Tee-Object -FilePath "$logDir\fetch_upcoming_$stamp.log"

Write-Host "`n=== fetch_results ===" -ForegroundColor Cyan
python fetch_results.py 2>&1 | Tee-Object -FilePath "$logDir\fetch_results_$stamp.log"

Write-Host "`n=== settle ===" -ForegroundColor Cyan
python settle.py 2>&1 | Tee-Object -FilePath "$logDir\settle_$stamp.log"

Write-Host "`n=== done ===" -ForegroundColor Green
