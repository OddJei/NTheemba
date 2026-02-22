$OutFile = "integration_run.txt"
if (Test-Path $OutFile) { Remove-Item $OutFile }
function Append($title, $obj) {
    "=== $title ===" | Out-File -FilePath $OutFile -Append -Encoding utf8
    if ($null -eq $obj) {
        "<no response>" | Out-File -FilePath $OutFile -Append -Encoding utf8
    } else {
        try {
            $json = $obj | ConvertTo-Json -Depth 10
        } catch {
            $json = $obj.ToString()
        }
        $json | Out-File -FilePath $OutFile -Append -Encoding utf8
    }
    "" | Out-File -FilePath $OutFile -Append -Encoding utf8
}

$headers = @{ Authorization = 'Bearer dummy-token' }
$intsec = @{ 'X-Internal-Secret' = 'secret' }

# 1) HYDRATE
Write-Host 'Running HYDRATE'
$body = '{"session_id":"sess-123","bot_phone":"+250700000020","user_phone":"+250700000021","platform":"test","payload":{"user_name":"Alice"}}'
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/api/v1/hydrate/session' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -ErrorAction Stop
    Append 'HYDRATE RESPONSE' $r
} catch {
    Append 'HYDRATE ERROR' $_.Exception.Response.StatusCode.Value__
}

# 2) RESERVE (include required cart_id, user_id, business_id)
Write-Host 'Running RESERVE'
$body = (@{
    session_id = 'sess-123'
    cart_id = 'cart-1'
    user_id = 'user-1'
    business_id = 'biz-1'
    amount_minor = 10000
    currency = 'ZMW'
    reason = 'order_hold'
} | ConvertTo-Json)
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/api/v1/reserve' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -ErrorAction Stop
    Append 'RESERVE RESPONSE' $r
} catch {
    Append 'RESERVE ERROR' ($_ | Out-String)
}

# 3) CONFIRM (use /api/v1/confirm)
Write-Host 'Running CONFIRM'
$body = (@{
    session_id = 'sess-123'
    payment_reference = '<use_reservation_id_if_returned>'
    amount_minor = 10000
    currency = 'ZMW'
} | ConvertTo-Json)
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/api/v1/confirm' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -ErrorAction Stop
    Append 'CONFIRM RESPONSE' $r
} catch {
    Append 'CONFIRM ERROR' ($_ | Out-String)
}

# 4) CREATE_CYCLE (use /api/v1/sessions/{id}/create_cycle)
Write-Host 'Running CREATE_CYCLE'
$body = (@{ reason = 'start_checkout'; meta = @{} } | ConvertTo-Json)
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/api/v1/sessions/sess-123/create_cycle' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -ErrorAction Stop
    Append 'CREATE_CYCLE RESPONSE' $r
} catch {
    Append 'CREATE_CYCLE ERROR' ($_ | Out-String)
}

# 5) UPDATE_STAGE (use /api/v1/sessions/{id}/update_stage)
Write-Host 'Running UPDATE_STAGE'
$body = (@{ stage = 'cart'; meta = @{} } | ConvertTo-Json)
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/api/v1/sessions/sess-123/update_stage' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -ErrorAction Stop
    Append 'UPDATE_STAGE RESPONSE' $r
} catch {
    Append 'UPDATE_STAGE ERROR' ($_ | Out-String)
}

# 6) LOG MESSAGE
Write-Host 'Running LOG MESSAGE'
$body = '{"session_id":"sess-123","level":"debug","message":"test log from integration","meta":{}}'
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/api/v1/messages/log' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -ErrorAction Stop
    Append 'LOG RESPONSE' $r
} catch {
    Append 'LOG ERROR' ($_ | Out-String)
}

# 7) POLL OUTBOX MSME
Write-Host 'Polling MSME outbox'
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8500/outbox/pending' -Method Get -Headers $intsec -ErrorAction Stop
    Append 'MSME OUTBOX' $r
} catch {
    Append 'MSME OUTBOX ERROR' ($_ | Out-String)
}

# 8) POLL OUTBOX AFFILIATE
Write-Host 'Polling AFFILIATE outbox'
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8510/outbox/pending' -Method Get -Headers $intsec -ErrorAction Stop
    Append 'AFF OUTBOX' $r
} catch {
    Append 'AFF OUTBOX ERROR' ($_ | Out-String)
}

# 9) DISPATCHER RUN_ONCE
Write-Host 'Triggering dispatcher run_once'
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8550/run_once' -Method Post -Headers $intsec -ErrorAction Stop
    Append 'DISPATCHER RUN_ONCE' $r
} catch {
    Append 'DISPATCHER RUN_ONCE ERROR' ($_ | Out-String)
}

Write-Host "Integration run complete. Results saved to $OutFile"
