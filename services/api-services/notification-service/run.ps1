#!/usr/bin/env pwsh
# Run the notification service on port 8285 (development)
Set-Location -Path $PSScriptRoot
. .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8285
