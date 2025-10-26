# Frontend Handoff — Financial Team

This document summarizes the frontend (dashboards) implementation relevant to billing, subscriptions, payments, and earnings analytics. Use this as the primary reference for integration, reconciliation, and financial reporting.

## Quick summary

- Project: dashboards (React + TypeScript + Vite + Tailwind)
- Demo URL (dev): `http://localhost:8090/subscription-demo` (Vite dev server)
- Key pages/components affecting finance:
  - `src/components/shared/SubscriptionPlans.tsx` — plan selection, pricing logic (monthly/yearly), savings calculation
  - `src/components/shared/SubscriptionManagement.tsx` — active subscription view, billing history placeholder, upgrade/downgrade flow
  - `src/components/shared/BillingPayment.tsx` — mobile money payment UI and flow (MTN/Airtel/Zamtel placeholders)
  - `src/components/shared/EarningsTracker.tsx` — break-even, ROI, net profit calculations used for recommendations
  - `src/pages/SubscriptionDemo.tsx` — integrated demo that exercises flows and mock data

## How to run locally (dev)

Use PowerShell on Windows as the repo was developed with Vite and tested on PowerShell.

```powershell
cd "c:\Users\SMART PC\Documents\NTheemba\services\Frontend\dashboards"
npm install        # first time only
npm run dev        # starts Vite dev server (default port 8089 -> falls back to 8090 in current session)
```

The live demo page is registered at `/subscription-demo` and the app uses React Router. The `App.tsx` file contains the top-level routes.


## Data contracts and shapes (frontend expectations)

Below are the shapes and fields the frontend expects; use them to define backend APIs and reconciliation outputs.

### Plan object (example)

```ts
interface Plan {
  id: string;                // 'basic' | 'pro' | 'elite'
  name: string;              // human-friendly
  monthlyPrice: number;      // in minor currency units or decimal (decide with backend)
  yearlyPrice?: number;      // optional, used to compute savings
  features: string[];
}
```

### Payment request payload (frontend -> backend)

```ts
interface PaymentRequest {
  provider: 'mtn' | 'airtel' | 'zamtel' | 'other';
  phone: string;            // E.164 preferred format
  amount: number;           // amount in major currency (or minor if agreed)
  currency: string;         // ISO currency e.g. 'ZMW'
  planId: string;
  billingInterval: 'monthly' | 'yearly';
  reference?: string;       // generated on frontend or backend for correlation
}
```

### Payment response (backend -> frontend)

```ts
interface PaymentResponse {
  status: 'pending' | 'success' | 'failed';
  providerRef?: string;   // provider reference id if available
  transactionId?: string; // backend transaction id
  message?: string;
}
```

### Subscription record (backend canonical)

```ts
interface Subscription {
  id: string;
  userId: string;
  planId: string;
  billingInterval: 'monthly' | 'yearly';
  status: 'active' | 'past_due' | 'cancelled' | 'trial' | 'pending';
  startedAt: string; // ISO timestamp
  nextBillingAt?: string; // ISO
}
```


## Financial flows to support (recommendations)

- Payment initiation: frontend posts `PaymentRequest` to backend endpoint (e.g. `POST /api/payments/charge`). Backend returns `PaymentResponse` and triggers provider call. Prefer backend to initiate provider call and return stable transaction id.
- Webhook reconciliation: provider -> backend -> update subscription/payment status. Financial team should request a webhook audit log and a daily reconciliation CSV export.
- Invoicing: create invoice records after payment success with line items: plan, tax, discount, currency, gross/net, fee (provider/processing). Include providerRef and transactionId.
- Refunds/Chargebacks: backend should keep immutable transaction records with refund status and amounts. Frontend shows refund status in `SubscriptionManagement`.


## Money/currency, taxes, and rounding

- Decide canonical currency unit: frontend currently uses decimal amounts (e.g., 50, 150). Backend should provide a single canonical currency and show decimals consistently. Prefer storing minor unit (cents/ngwee) on the server to avoid rounding errors.
- For yearly discounts, frontend shows savings computed as ((monthlyPrice * 12) - yearlyPrice).


## Reporting & reconciliation artifacts to produce

- Daily transactions CSV with these columns: transactionId, providerRef, userId, amountMinor, currency, feeMinor, netMinor, status, planId, startedAt, completedAt
- Monthly subscription summary (plan counts, MRR, ARR, churn rate)
- Payouts to affiliates (if affiliate-driven sales) — commission calculation rules are executed in backend; frontend earnings tracker is for display only.


## Test & QA scenarios (finance-focused)

1. Successful payment (MTN) — ensure webhook marks transaction success and subscription is active.
2. Failed payment attempt — check `past_due` and retry logic.
3. Refund issued — ensure invoice/transaction audit contains refund row and net is adjusted.
4. Yearly billing — ensure renewal date and savings calculation are correct.
5. Currency mismatch — ensure error handling and clear messaging to users.


## Logs, audit and retention

- Keep payment-related logs (requests/responses, provider refs) for at least 7 years if required by local regulations; consult Legal team.
- Require immutable transaction records in backend storage. Frontend only reads and displays.

## Next steps for Financial Team (recommended)

1. Define exact API endpoints and contract (JSON schema) using the shapes above.
2. Specify the currency/minor-unit convention and rounding rules.
3. Request webhook test keys from each provider and define retry/backoff policy.
4. Create reconciliation report templates and schedule (daily/weekly/monthly).
5. Coordinate with Legal team on retention and compliance rules.


## Code pointers (useful file paths)

- `src/components/shared/SubscriptionPlans.tsx`
- `src/components/shared/SubscriptionManagement.tsx`
- `src/components/shared/BillingPayment.tsx`
- `src/components/shared/EarningsTracker.tsx`
- `src/pages/SubscriptionDemo.tsx`
- `src/App.tsx` (top-level routes)

---
If you'd like, I can also generate an OpenAPI/JSON Schema draft for the payment and subscription endpoints to hand to the backend team.
