# NTheemba Mini Dashboards

Minimal implementation of NTheemba dashboards with direct API integration.

## Features

- **Landing Page**: Marketing homepage with dashboard access
- **Affiliate Dashboard**: Track clicks, earnings, campaigns, and payouts
- **MSME Dashboard**: Business metrics, sales, inventory, and quick actions
- **Admin Dashboard**: Platform oversight, user management, and system health

## Tech Stack

- React 18 + TypeScript
- Vite
- TailwindCSS + shadcn/ui components
- React Router
- TanStack Query
- Axios

## API Integration

Backend API: `http://localhost:8980`

### Key Endpoints

#### Affiliate
- `GET /affiliate/stats` - Dashboard statistics
- `GET /affiliate/campaigns` - Campaign list
- `GET /affiliate/earnings` - Earnings history
- `POST /affiliate/payout` - Request payout

#### MSME
- `GET /msme/stats` - Dashboard statistics  
- `GET /msme/products` - Product list
- `POST /msme/products` - Add product
- `GET /msme/orders` - Order list

#### Admin
- `GET /admin/stats` - Platform statistics
- `GET /admin/users` - User list
- `GET /admin/approvals` - Pending approvals
- `GET /admin/activity` - Recent activity

#### Auth
- `POST /auth/login` - Login (returns accessToken, refreshToken, role)
- `POST /auth/refresh` - Refresh access token

## Setup

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

## Environment Variables

Create `.env` file:

```
VITE_API_URL=http://localhost:8980
```

## Alignment with Backend

Based on `FRONTEND_ENTITY_ALIGNMENTS.txt`, this implementation focuses on:

### Aligning Parts (Implemented)
- ✅ Users / Profiles & Auth
- ✅ MSME profile & dashboard
- ✅ Products & Services UI
- ✅ Campaigns & Links
- ✅ Affiliate dashboard & earnings tracker
- ✅ Analytics / Insights panels

### Missing Backend Endpoints (Needed)
- Order Items & multi-item cart
- Payment webhooks & transactions
- Affiliate payouts & earnings records
- Click events & conversion tracking
- Inventory movements & alerts
- Service bookings & reviews
- Session management & OTP
- Audit logs

## Demo Mode

Click "Demo as [Role]" on login page to explore without backend connection.

## Project Structure

```
src/
├── components/
│   └── ui/          # shadcn/ui components
├── lib/
│   ├── api.ts       # Axios client
│   ├── auth.ts      # Token storage
│   ├── authContext.tsx  # Auth provider
│   └── utils.ts     # Utilities
├── pages/
│   ├── Landing.tsx
│   ├── Login.tsx
│   ├── AffiliateDashboard.tsx
│   ├── MSMEDashboard.tsx
│   └── AdminDashboard.tsx
├── App.tsx
├── main.tsx
└── index.css
```

## Next Steps

1. Implement real backend endpoints
2. Add payment gateway integration
3. Implement click tracking
4. Add payout workflows
5. Implement booking system
6. Add audit logging
