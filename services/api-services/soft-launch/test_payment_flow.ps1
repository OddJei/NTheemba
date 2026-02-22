# Test script for payment revenue endpoints simulation
# Simulates subscription -> buying a product: deposit -> MSME payout -> Affiliate payout

$baseUrl = "http://127.0.0.1:8590"
$msmeBaseUrl = "http://127.0.0.1:8500"
$orderId = "test-order-$(Get-Random)"
$businessId = "test-biz-123"
$customerPhone = "260771234567"
$msmePhone = "260771234567"  # Same for simplicity
$affiliatePhone = "260772345678"
$amountMinor = 10000  # 100 ZMW
$subscriptionAmountMinor = 5000  # 50 ZMW
$affiliateAmountMinor = 500  # 5 ZMW

Write-Host "Starting payment flow simulation"

# Step 0: Use provided service token
Write-Host "0. Using provided service token..."
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZmZpbGlhdGVfaWQiOm51bGwsImJ1c2luZXNzX2lkIjoiMDcwNmJiODEtNzNkOC00NjMyLThlZDgtNjRlOTBiNTI3NzIxIiwiZXhwIjoxNzcxMTYyNTIzLCJpYXQiOjE3NzExNTg5MjMsInJvbGUiOiJtc21lIiwic3ViIjoiNmZhMDU2OTctOThmMy00NjUyLTkxYjAtZTRmNDBhODZjODIyIiwidHlwIjoiYWNjZXNzIn0.W0GWBG5AADliFQZNp2cm9MLnn-8FlEe5pMr51AdQbRg"
$authHeader = @{ "Authorization" = "Bearer $token" }
Write-Host "Token set"

# Step 1: Initiate subscription payment
Write-Host "1. Initiating subscription payment..."
$subscriptionBody = @{
    order_id = "sub-$orderId"
    business_id = $businessId
    amount_minor = $subscriptionAmountMinor
    currency = "ZMW"
    phoneNumber = $customerPhone
    paymentType = "subscription"
    metadata = @{
        source = "test-simulation"
        plan = "premium"
        paid_until = "2026-03-15T00:00:00"
    }
} | ConvertTo-Json

$subscriptionResponse = Invoke-RestMethod -Uri "$baseUrl/pawapay/deposits/initiate" -Method Post -Body $subscriptionBody -ContentType "application/json" -Headers (@{ "X-Idempotency-Key" = [guid]::NewGuid().ToString() } + $authHeader)
Write-Host "Subscription initiated: $($subscriptionResponse | ConvertTo-Json -Depth 3)"

# Step 2: Initiate deposit (customer buying product)
Write-Host "2. Initiating deposit for product purchase..."
$depositBody = @{
    order_id = $orderId
    business_id = $businessId
    amount_minor = $amountMinor
    currency = "ZMW"
    phoneNumber = $customerPhone
    paymentType = "one_time"
    metadata = @{
        source = "test-simulation"
        platform_fee_minor = 1000  # 10 ZMW fee
    }
} | ConvertTo-Json

$depositResponse = Invoke-RestMethod -Uri "$baseUrl/pawapay/deposits/initiate" -Method Post -Body $depositBody -ContentType "application/json" -Headers (@{ "X-Idempotency-Key" = [guid]::NewGuid().ToString() } + $authHeader)
Write-Host "Deposit initiated: $($depositResponse | ConvertTo-Json -Depth 3)"

# Step 3: Get settlement details
Write-Host "3. Fetching settlement details..."
$settlementResponse = Invoke-RestMethod -Uri "$baseUrl/settlements/$orderId" -Method Get -Headers $authHeader
Write-Host "Settlement: $($settlementResponse | ConvertTo-Json -Depth 3)"

# Step 4: Initiate MSME payout
Write-Host "4. Initiating MSME payout..."
$msmePayoutBody = @{
    order_id = $orderId
    business_id = $businessId
    msme_phone = $msmePhone
    order_amount_minor = $amountMinor
    currency = "ZMW"
    metadata = @{
        source = "test-simulation"
    }
} | ConvertTo-Json

$msmePayoutResponse = Invoke-RestMethod -Uri "$baseUrl/msme/payouts/initiate" -Method Post -Body $msmePayoutBody -ContentType "application/json" -Headers $authHeader
Write-Host "MSME Payout initiated: $($msmePayoutResponse | ConvertTo-Json -Depth 3)"

# Step 5: Initiate Affiliate payout
Write-Host "5. Initiating Affiliate payout..."
$affiliatePayoutBody = @{
    order_id = $orderId
    business_id = $businessId
    amount_minor = $affiliateAmountMinor
    currency = "ZMW"
    phoneNumber = $affiliatePhone
    payoutType = "affiliate"
    metadata = @{
        source = "test-simulation"
        affiliate_id = "test-aff-123"
    }
} | ConvertTo-Json

$affiliatePayoutResponse = Invoke-RestMethod -Uri "$baseUrl/pawapay/payouts/initiate" -Method Post -Body $affiliatePayoutBody -ContentType "application/json" -Headers (@{ "X-Idempotency-Key" = [guid]::NewGuid().ToString() } + $authHeader)
Write-Host "Affiliate Payout initiated: $($affiliatePayoutResponse | ConvertTo-Json -Depth 3)"

Write-Host "Simulation complete. Check database for subscriptions, settlements, platform_fees, msme_payouts, affiliate_payouts tables."