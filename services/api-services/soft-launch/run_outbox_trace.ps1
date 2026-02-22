$internal = '0a1b2c3d-4e5f-6789-abcd-ef0123456789'
$hdr = @{ 'X-Internal-Secret' = $internal }

try {
    $bs = Invoke-RestMethod -Uri 'http://localhost:8500/internal/businesses' -Headers $hdr -TimeoutSec 30
} catch {
    Write-Host "ERROR fetching businesses: $_"
    exit 1
}
if (-not $bs -or $bs.Count -eq 0) {
    Write-Host "No businesses returned"
    exit 1
}
$bid = $bs[0].id
Write-Host "BUSINESS: $bid"

try {
    $tok = Invoke-RestMethod -Uri "http://localhost:8500/auth/service-token/$bid" -Method Post -Body '{}' -ContentType 'application/json' -TimeoutSec 30
} catch {
    Write-Host "ERROR requesting token: $_"
    exit 1
}
$token = $tok.access_token
Write-Host "TOKEN: $token"

$body = @{ 
    plan = 'paid';
    amount_minor = 1000;
    currency = 'ZMW';
    phone_number = '0977123456';
    provider = 'pawapay'
} | ConvertTo-Json

try {
    $resp = Invoke-RestMethod -Uri "http://localhost:8500/business/$bid/subscribe_and_pay" -Method Post -Headers @{ Authorization = "Bearer $token"; 'Content-Type' = 'application/json' } -Body $body -TimeoutSec 120
    Write-Host "SUBSCRIBE-RESP:`n" ($resp | ConvertTo-Json -Depth 5)
} catch {
    Write-Host "ERROR subscribe_and_pay: $_"
    exit 1
}

exit 0
