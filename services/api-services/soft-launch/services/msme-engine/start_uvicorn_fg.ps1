$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:!ladybug!#!@127.0.0.1:5432/ntheemba?options=-c%20search_path%3Dmsme_engine'
$env:OUTBOX_INTERNAL_SECRET = 'testsecret'
Write-Output "DATABASE_URL: $env:DATABASE_URL"
Write-Output "OUTBOX_INTERNAL_SECRET: $env:OUTBOX_INTERNAL_SECRET"
Write-Output 'Starting uvicorn foreground (debug logs)...'
& '.\.venv\Scripts\python.exe' -u -m uvicorn src.app.main:app --host 127.0.0.1 --port 8500 --log-level debug
