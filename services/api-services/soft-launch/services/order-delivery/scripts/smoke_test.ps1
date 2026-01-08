param(
  [int]$Port = 8540
)

$ErrorActionPreference = "Stop"

$ServiceDir = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $ServiceDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  $Py = "python"
}

Write-Host "[smoke] Using python: $Py"
Write-Host "[smoke] Service dir: $ServiceDir"

Push-Location $ServiceDir
try {
  & $Py -m pip install -q -r requirements.txt

  Write-Host "[smoke] Starting API on port $Port..."
  $outLog = Join-Path $ServiceDir "smoke_uvicorn.out.log"
  $errLog = Join-Path $ServiceDir "smoke_uvicorn.err.log"
  if (Test-Path $outLog) { Remove-Item $outLog -Force -ErrorAction SilentlyContinue }
  if (Test-Path $errLog) { Remove-Item $errLog -Force -ErrorAction SilentlyContinue }

  $proc = Start-Process -FilePath $Py -ArgumentList @(
    "-m","uvicorn","src.app.main:app",
    "--host","127.0.0.1",
    "--port",$Port
  ) -WorkingDirectory $ServiceDir -PassThru -NoNewWindow -RedirectStandardOutput $outLog -RedirectStandardError $errLog

  try {
    $base = "http://127.0.0.1:$Port"

    $deadline = (Get-Date).AddSeconds(20)
    do {
      if ($proc.HasExited) {
        Write-Host "[smoke] Uvicorn exited early (code=$($proc.ExitCode)). Logs:"
        if (Test-Path $errLog) { Get-Content $errLog -Tail 200 | Write-Host }
        if (Test-Path $outLog) { Get-Content $outLog -Tail 200 | Write-Host }
        throw "uvicorn_failed_to_start"
      }
      try {
        $h = Invoke-RestMethod -Method GET -Uri "$base/health" -TimeoutSec 2
        if ($h.status -eq "ok") { break }
      } catch {
        Start-Sleep -Milliseconds 300
      }
    } while ((Get-Date) -lt $deadline)

    $h = Invoke-RestMethod -Method GET -Uri "$base/health" -TimeoutSec 5
    Write-Host "[smoke] health: $($h | ConvertTo-Json -Compress)"

    $orderPayload = @{
      session_id = "sess_smoke"
      user_phone = "+27000000000"
      user_id = $null
      business_id = "business_smoke"
      delivery_method = "pickup"
      total_amount = 12500
      currency = "ZAR"
      metadata = @{ cart_id = "cart_smoke" }
    }

    $order = Invoke-RestMethod -Method POST -Uri "$base/orders/create" -ContentType "application/json" -Body ($orderPayload | ConvertTo-Json -Depth 6)
    Write-Host "[smoke] order_create: id=$($order.id) status=$($order.status)"

    $paid = Invoke-RestMethod -Method POST -Uri "$base/orders/$($order.id)/mark_paid" -TimeoutSec 10
    Write-Host "[smoke] order_mark_paid: status=$($paid.status)"

    $init = Invoke-RestMethod -Method POST -Uri "$base/delivery/initiate/$($order.id)" -TimeoutSec 10
    Write-Host "[smoke] delivery_initiate: delivery_id=$($init.delivery.id) code=$($init.delivery_code)"

    if ($init.delivery_code -eq "******") {
      throw "delivery_code was masked; smoke test needs fresh delivery creation"
    }

    $confirmPayload = @{
      delivery_code = $init.delivery_code
      confirmed_by = "smoke_test"
    }

    $conf = Invoke-RestMethod -Method POST -Uri "$base/delivery/$($init.delivery.id)/confirm" -ContentType "application/json" -Body ($confirmPayload | ConvertTo-Json -Depth 6) -TimeoutSec 10
    Write-Host "[smoke] delivery_confirm: status=$($conf.status) confirmed_by=$($conf.confirmed_by)"

    $order2 = Invoke-RestMethod -Method GET -Uri "$base/orders/$($order.id)" -TimeoutSec 10
    Write-Host "[smoke] order_get: status=$($order2.status)"

    if ($order2.status -ne "delivered") { throw "expected delivered order" }
    if ($conf.status -ne "confirmed") { throw "expected confirmed delivery" }

    Write-Host "[smoke] OK"
  } finally {
    Write-Host "[smoke] Stopping API (pid=$($proc.Id))"
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  }
} finally {
  Pop-Location
}
