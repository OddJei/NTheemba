# Register user → register business → subscribe & pay (local)

This documents the working happy-path flow implemented in the Soft Launch bundle using:

- **MSME Engine**: `http://localhost:8500`
- **Payment + Revenue**: `http://localhost:8590`
- **Audit Service**: `http://localhost:8290`

## 0) Start services

From repo root:

```powershell
cd "C:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch"
docker compose up -d --build msme-engine payment-revenue audit-service postgres
```

(You can run the full stack too; this is the minimum for the cycle.)

## 1) Register a user (MSME Engine)

Endpoint: `POST /auth/register`

**PowerShell**

```powershell
$base = 'http://localhost:8500'
$suffix = (New-Guid).Guid.Substring(0,8)

$user = @{
  username = "testowner_$suffix"
  email    = "owner_$suffix@test.com"
  phone    = '260973456789'
  password = 'Test123!'
}

$r = Invoke-RestMethod -Method Post -Uri "$base/auth/register" -ContentType 'application/json' -Body ($user | ConvertTo-Json)
$r.id
```

Response includes the new user `id`.

## 2) Register a business (MSME Engine)

Endpoint: `POST /business/register`

You can register a business in two ways:

- Create an owner user inline using `owner` (owner object)
- Link an existing user using `owner_user_id`

This flow uses `owner_user_id`.

**PowerShell**

```powershell
$biz = @{
  name              = "Test MSME $suffix"
  owner_user_id     = $r.id
  location          = 'Lusaka'
  category          = 'retail'
  subscription_plan = 'free'
}

$bizResp = Invoke-RestMethod -Method Post -Uri "$base/business/register" -ContentType 'application/json' -Body ($biz | ConvertTo-Json)
$businessId = $bizResp.business.id
$businessId
```

## 3) Login (get Bearer token)

Endpoint: `POST /auth/login`

**PowerShell**

```powershell
$login = @{ identifier = $user.email; password = $user.password }
$loginResp = Invoke-RestMethod -Method Post -Uri "$base/auth/login" -ContentType 'application/json' -Body ($login | ConvertTo-Json)
$token = $loginResp.access_token
$token
```

## 4) Subscribe and initiate payment

Endpoint: `POST /business/{business_id}/subscribe_and_pay`

Important requirements:

- Must include `Authorization: Bearer <token>` (payment initiation requires auth)
- `amount_minor` is an integer in minor currency units (example: `5000` = 50.00 ZMW)
- `provider` must be a valid pawaPay provider code, e.g.:
  - `AIRTEL_OAPI_ZMB`
  - `MTN_MOMO_ZMB`
  - `ZAMTEL_ZMB`
- `phone_number` can use sandbox test MSISDNs (see `services/payment-revenue/pawapay docs.txt`)

**PowerShell**

```powershell
$sub = @{
  plan         = 'paid'
  amount_minor = 5000
  phone_number = '260973456789'
  provider     = 'MTN_MOMO_ZMB'
  currency     = 'ZMW'
}

$headers = @{ Authorization = "Bearer $token"; 'X-Correlation-Id' = "audit-test-$suffix" }
$subResp = Invoke-RestMethod -Method Post -Uri "$base/business/$businessId/subscribe_and_pay" -Headers $headers -ContentType 'application/json' -Body ($sub | ConvertTo-Json)
$subResp
```

Expected result:

- MSME Engine returns `201`
- Response includes:
  - `subscription.status` set to `pending_payment`
  - `payment_request.payment_revenue_response.status` usually `ACCEPTED` (sandbox)

## 5) Verify audit events

The MSME Engine emits audit events to Audit Service. You can query them like this:

```powershell
Invoke-RestMethod -Method Get -Uri 'http://localhost:8290/audit/?service=msme-engine&event_type=subscription_initiated'
```

You should see an item with your correlation id (e.g. `audit-test-...`).

## Option A) Run the repo’s working end-to-end script

This repo includes a script that runs the full sequence (register user → business → login → subscribe_and_pay).

```powershell
cd "C:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch"
$py = Join-Path $PWD ".venv\Scripts\python.exe"
& $py "scripts\audit_flow_test.py"
```

If it succeeds, it prints `subscribe_and_pay 201` and a JSON response including the payment initiation payload.
