$ErrorActionPreference = 'Stop'
# Stop any existing uvicorn processes
# Also free port 8500 if some other process is holding it
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
# Also free port 8500 if some other process is holding it
$portPid = (Get-NetTCPConnection -LocalPort 8500 -ErrorAction SilentlyContinue).OwningProcess
if ($portPid) {
	Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
	Write-Output "killed process using port 8500: $portPid"
}
# Change to the msme-engine directory (script lives in that folder)
Set-Location $PSScriptRoot
# Set environment variables for this process
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:!ladybug!#!@127.0.0.1:5432/ntheemba?options=-c%20search_path%3Dmsme_engine'
$env:OUTBOX_INTERNAL_SECRET = 'testsecret'
# Start uvicorn in the background and redirect logs
Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','src.app.main:app','--host','127.0.0.1','--port','8500','--log-level','info' -NoNewWindow -RedirectStandardOutput '..\uvicorn.out.log' -RedirectStandardError '..\uvicorn.err.log' -PassThru
Write-Output 'uvicorn start command executed.'
Start-Sleep -Seconds 4
try {
	$r = Invoke-RestMethod -Uri 'http://127.0.0.1:8500/health' -Method Get -TimeoutSec 5
	Write-Output "HEALTH_OK: $(ConvertTo-Json $r)"
} catch {
	Write-Output "HEALTH_ERR: $($_.Exception.Message)"
	if (Test-Path '..\uvicorn.err.log') {
		Write-Output '--- uvicorn.err.log ---'
		Get-Content '..\uvicorn.err.log' -Tail 200
	}
}
