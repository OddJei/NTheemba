# MTN Gateway (scaffold)

Minimal Node.js scaffold for the MTN payment gateway adapter.

Quick start (PowerShell):

```powershell
cd "services\getways\payment getway\mtn"
npm install
copy .env.example .env
$env:MTN_API_KEY = "your-key"
npm run start
```

Endpoints:

- POST /mtn/charge  — initiate a charge (payload: amount, currency, phone, order_ref)
- POST /mtn/verify  — verify a transaction (payload: transaction_ref)
