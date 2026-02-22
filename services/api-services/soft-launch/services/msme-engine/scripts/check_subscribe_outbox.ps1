 # Simple smoke-test to call subscribe_and_pay and verify an Outbox event.
 # Usage:
 #   $env:MSME_TOKEN = '<JWT HERE>'
 #   $env:MSME_INTERNAL_SECRET = '<internal secret>'
 #   .\check_subscribe_outbox.ps1 -BusinessId '<business-id>'
 param(
     [Parameter(Mandatory=$true)]
     [string]$BusinessId
 )
 $base = 'http://localhost:8500'
 $token = $env:MSME_TOKEN
 $internal = $env:MSME_INTERNAL_SECRET
 if (-not $token) { Write-Error "Set MSME_TOKEN env var to a valid access token"; exit 2 }
 if (-not $internal) { Write-Error "Set MSME_INTERNAL_SECRET env var to the internal secret"; exit 2 }
 $h = @{ Authorization = "Bearer $token" }
 $body = @{ plan='paid'; amount_minor=5000; currency='ZMW'; phone_number='+260970000001'; provider='pawapay' } | ConvertTo-Json
 Write-Host "Calling subscribe_and_pay for business $BusinessId..."
 try{
     $resp = Invoke-RestMethod -Uri "$base/business/$BusinessId/subscribe_and_pay" -Method POST -Headers $h -Body $body -ContentType 'application/json'
     Write-Host "subscribe_and_pay response:`n" ($resp | ConvertTo-Json -Depth 5)
 } catch {
     Write-Error "subscribe_and_pay failed: $($_.Exception.Message)"
     exit 3
 }
 # extract reference id
 $ref = $resp.payment_request.reference_id
 if (-not $ref) { Write-Warning "No payment reference found in response" }
 Write-Host "Waiting 1s then querying /outbox/pending for events referencing $ref..."
 Start-Sleep -Seconds 1
 try{
     $out = Invoke-RestMethod -Uri "$base/outbox/pending" -Method GET -Headers @{ 'X-Internal-Secret' = $internal }
 } catch {
     Write-Error "Failed to fetch /outbox/pending: $($_.Exception.Message)"; exit 4
 }
 # search for events containing the reference id
 $found = $false
 foreach ($e in $out) {
     $j = $null
     try { $j = $e.payload | ConvertFrom-Json -ErrorAction Stop } catch {}
     if ($j -and $j.metadata -and $j.metadata.reference_id -eq $ref) { Write-Host "Found matching outbox event id: $($e.id)"; $found = $true; break }
 }
 if (-not $found) { Write-Warning "No matching outbox event found for reference $ref"; exit 5 }
 Write-Host "OK: Outbox event exists for payment initiation (reference: $ref)"