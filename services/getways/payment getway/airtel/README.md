# Airtel Gateway (scaffold)

Minimal Node.js scaffold for the Airtel payment gateway adapter.

Quick start (PowerShell):

```powershell
cd "services\getways\payment getway\airtel"
npm install
copy .env.example .env
$env:AIRTEL_API_KEY = "your-key"
npm run start
```

Endpoints:

- POST /airtel/charge  — initiate a charge (payload: amount, currency, phone, order_ref)
- POST /airtel/verify  — verify a transaction (payload: transaction_ref)
