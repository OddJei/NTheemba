$adminKey = "change-me"
$affiliateBase = "http://localhost:8510"
$paymentBase = "http://localhost:8590"

Write-Host "[1] Open or get current epoch"
$epoch = Invoke-RestMethod -Method Post -Uri "$affiliateBase/admin/epochs/open" -Headers @{"X-Admin-Key"=$adminKey}
$epochId = $epoch.id
Write-Host "Epoch: $epochId"

Write-Host "[2] Create affiliates and seed payment events"
$now = (Get-Date).ToUniversalTime().ToString("o")
$affiliateNames = @("Test Affiliate 1", "Test Affiliate 2", "Test Affiliate 3")
$affiliateIds = @()

foreach ($name in $affiliateNames) {
	$created = Invoke-RestMethod -Method Post -Uri "$affiliateBase/affiliates" -Headers @{"X-Admin-Key"=$adminKey} -ContentType "application/json" -Body (@{ name = $name } | ConvertTo-Json)
	$affiliateIds += $created.id
}

foreach ($affId in $affiliateIds) {
	$paymentEvent = @{
		event_id = [Guid]::NewGuid().ToString()
		event_type = "payment_success"
		occurred_at = $now
		correlation_id = [Guid]::NewGuid().ToString()
		producer = "payment-revenue"
		payment_id = [Guid]::NewGuid().ToString()
		order_id = $affId
		business_id = "BIZ-001"
		user_phone = "260700000999"
		amount = 1000.0
		currency = "ZMW"
		earnings = @{
			msme_amount = 900.0
			affiliate_amount = 80.0
			platform_amount = 20.0
			affiliate_id = $affId
		}
	}

	Invoke-RestMethod -Method Post -Uri "$affiliateBase/events/payment-success" -ContentType "application/json" -Body ($paymentEvent | ConvertTo-Json -Depth 6) | Out-Null
}

Write-Host "[3] Set gross revenue"
Invoke-RestMethod -Method Put -Uri "$affiliateBase/admin/epochs/$epochId/gross-revenue" -Headers @{"X-Admin-Key"=$adminKey} -ContentType "application/json" -Body '{"gross_revenue_zmw": 50000}' | Out-Null

Write-Host "[4] Close epoch"
Invoke-RestMethod -Method Post -Uri "$affiliateBase/admin/epochs/$epochId/close" -Headers @{"X-Admin-Key"=$adminKey} | Out-Null

Write-Host "[5] Fetch allocations"
$allocations = Invoke-RestMethod -Method Get -Uri "$affiliateBase/admin/epochs/$epochId/allocations" -Headers @{"X-Admin-Key"=$adminKey}
$allocations = @($allocations)
Write-Host "Allocations: $($allocations.Count)"

if ($allocations.Count -lt 1) { throw "No allocations created" }

$payouts = $allocations | Select-Object -First 3 | ForEach-Object { @{ affiliate_id = $_.affiliate_id; amount_zmw = [double]$_.payout_zmw; currency = "ZMW" } }
$payload = @{ epoch_id = $epochId; callback_url = "http://affiliate-engine:8510/callbacks/payout-status"; payouts = $payouts } | ConvertTo-Json -Depth 6

Write-Host "[6] Initiate batch payout"
$resp = Invoke-RestMethod -Method Post -Uri "$paymentBase/payout/batch" -Headers @{"X-Admin-Key"=$adminKey} -ContentType "application/json" -Body $payload
$resp | ConvertTo-Json -Depth 6

Write-Host "[7] Done. Check logs for callbacks."