# Pawapay Gateway (scaffold)

This is a minimal Node.js scaffold for the Pawapay payment gateway adapter.

Quick start (PowerShell):

1. Install dependencies and run in development mode:

```powershell
cd "services\getways\payment getway\pawapay"
npm install
cp .env.example .env
$env:PAWAPAY_API_KEY = "your-key"  # or edit .env
npm run start
```

2. Endpoints:
- POST /pawapay/charge  — initiate a charge (payload: amount, currency, phone, order_ref)
- POST /pawapay/verify  — verify a transaction (payload: transaction_ref)

Notes:
- Adapter is a lightweight scaffold. Replace `src/services/pawapayAdapter.js` with the real API integration.
