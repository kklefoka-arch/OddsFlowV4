# OddsFlow V4 — Start server + ngrok
# Run from C:\OddsFlowV4

Set-Location C:\OddsFlowV4

# Start ngrok in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http 8083"

# Start uvicorn in this window
uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload
