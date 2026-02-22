try {
  $r = (Invoke-WebRequest -Uri 'http://localhost:3001' -UseBasicParsing -Method GET).StatusCode
  Write-Host "DASHBOARD_STATUS: $r"
} catch {
  Write-Host "DASHBOARD_ERR: $($_.Exception.Message)"
}

$body = @{ 
  profile = @{ 
    fullName = 'Live UI Test'
    email = 'live-ui+msme@example.com'
    phone = '+260700000099'
    location = 'Lusaka'
  }
  business = @{ 
    businessName = 'Live UI Biz'
    businessType = 'Retail'
    description = 'Live UI test'
  }
  products = @( 
    @{ name = 'Soap'; category = 'Hygiene'; price = '5'; initialStock = '10' } 
  )
} | ConvertTo-Json -Depth 6

try {
  $resp = Invoke-RestMethod -Uri 'http://localhost:8500/msme/onboard' -Method POST -Body $body -ContentType 'application/json'
  $resp | ConvertTo-Json -Depth 8 | Write-Host
} catch {
  Write-Host 'MSME_ONBOARD_ERR:' $_.Exception.Message
  if ($_.Exception.Response) {
    try { $_.Exception.Response.Content.ReadAsStringAsync() | Write-Host } catch { }
  }
}
