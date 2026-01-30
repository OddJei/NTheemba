#!/usr/bin/env pwsh
# Run the audit service on port 8290 (development)
Set-Location -Path $PSScriptRoot
. .\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8290
