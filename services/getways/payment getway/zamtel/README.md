# Zamtel Gateway (scaffold)

Minimal Node.js scaffold for the Zamtel payment gateway adapter.

Quick start (PowerShell):

```powershell
cd "services\getways\payment getway\zamtel"
npm install
copy .env.example .env
$env:ZAMTEL_API_KEY = "your-key"
npm run start
```

Endpoints:

- POST /zamtel/charge  — initiate a charge (payload: amount, currency, phone, order_ref)
- POST /zamtel/verify  — verify a transaction (payload: transaction_ref)
