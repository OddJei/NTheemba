$body = @{
    epoch_id = "2024-11-epoch-1"
    callback_url = "http://affiliate-engine:8510/callbacks/payout-status"
    payouts = @(
        @{
            affiliate_id = "aff-001"
            amount_zmw = 1500
            currency = "ZMW"
        },
        @{
            affiliate_id = "aff-002"
            amount_zmw = 2300
            currency = "ZMW"
        },
        @{
            affiliate_id = "aff-003"
            amount_zmw = 800
            currency = "ZMW"
        }
    )
} | ConvertTo-Json -Depth 10

Write-Host "Request body:"
Write-Host $body
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8590/payout/batch" -Method POST `
      -Headers @{"Content-Type"="application/json"; "X-Admin-Key"="change-me"} `
      -Body $body -TimeoutSec 10

    Write-Host "Response:"
    $response | ConvertTo-Json -Depth 10
    Write-Host ""
    Write-Host "Status: 202 Accepted"
    Write-Host "Batch ID: $($response.batch_id)"
    Write-Host "Total Payouts: $($response.total_payouts)"
    Write-Host "Total Amount: $($response.total_amount_zmw) ZMW"
} catch {
    Write-Host "Error: $_"
    Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)"
}
