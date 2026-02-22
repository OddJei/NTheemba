# NTheemba Mini Dashboards - Implementation Plan

## Overview
This document outlines the implementation of minimal NTheemba dashboards aligned with the backend API running on port 8980.

## Architecture

### Frontend Stack
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: TailwindCSS + shadcn/ui
- **Routing**: React Router v6
- **State**: TanStack Query
- **HTTP**: Axios with interceptors
- **Port**: 3000 (dev server)

### Backend Integration
- **API Base**: `http://localhost:8980`
- **Auth**: JWT with access/refresh tokens
- **Storage**: localStorage for tokens
- **Error Handling**: Axios interceptors with retry logic

## Pages Implemented

### 1. Landing Page (`/`)
**Purpose**: Marketing homepage and dashboard selector

**Features**:
- Hero section with platform overview
- Three feature cards (MSME, Affiliate, Admin)
- Platform statistics
- Call-to-action buttons
- Navigation to login and dashboards

**Routes**:
- `/` → Landing page
- Buttons navigate to `/login`, `/msme`, `/affiliate`, `/admin`

---

### 2. Login Page (`/login`)
**Purpose**: Authentication and demo access

**Features**:
- Email/password form
- Real API integration to `POST /auth/login`
- Demo mode buttons (no backend required)
- Role-based redirect after login
- Token storage in localStorage
- Error handling

**API Contract**:
```typescript
POST /auth/login
Request: { email: string, password: string }
Response: {
  accessToken: string,
  refreshToken: string,
  role: 'msme' | 'affiliate' | 'admin',
  user: { id, name, email }
}
```

---

### 3. Affiliate Dashboard (`/affiliate`)
**Purpose**: Track affiliate performance and earnings

**Aligning Parts** (from FRONTEND_ENTITY_ALIGNMENTS.txt):
- ✅ Affiliate dashboard UI
- ✅ Link tracking UI
- ✅ Earnings tracker
- ✅ Campaign UI

**Metrics Displayed**:
- Clicks this week (with trend)
- MSMEs helped (active partnerships)
- Earnings to-date (ZMW)
- Monthly goal progress (%)

**Sections**:
1. **Impact Snapshot** (4 metric cards)
2. **Active Campaigns** (list with status badges)
3. **Recent Earnings** (commission list)
4. **Upcoming Payout** (scheduled payment info)

**API Endpoints**:
```typescript
GET /affiliate/stats
Response: {
  clicksThisWeek: number,
  msmesHelped: number,
  earningsToDate: number,
  monthlyGoal: number,
  monthlyGoalProgress: number
}

GET /affiliate/campaigns
Response: Campaign[]

POST /affiliate/payout
Request: { amount: number, method: string }
```

**Missing Backend Features** (from alignment doc):
- ❌ Click events ingestion
- ❌ Conversion attribution
- ❌ Payout request endpoint
- ❌ Affiliate earnings records

---

### 4. MSME Dashboard (`/msme`)
**Purpose**: Business management and analytics

**Aligning Parts**:
- ✅ MSME dashboard UI
- ✅ Products UI skeletons
- ✅ Sales analytics
- ✅ Campaign UI

**Metrics Displayed**:
- Today's sales (ZMW with % change)
- New messages (inquiries + orders)
- Low stock items (alert count)
- Active campaigns (seasonal, launch)

**Sections**:
1. **Quick Stats** (4 metric cards)
2. **Business Health Meter** (87% with sub-metrics)
3. **Weekly Sales Overview** (7-day bar chart)
4. **Quick Actions** (4 action buttons)

**API Endpoints**:
```typescript
GET /msme/stats
Response: {
  todaysSales: number,
  newMessages: number,
  lowStockItems: number,
  activeCampaigns: number,
  businessHealth: number,
  weeklySales: number
}

GET /msme/products
Response: Product[]

POST /msme/products
Request: Product

GET /msme/orders
Response: Order[]
```

**Missing Backend Features**:
- ❌ Order items tracking
- ❌ Stock movement audit trail
- ❌ Inventory alerts
- ❌ Multi-item cart flows

---

### 5. Admin Dashboard (`/admin`)
**Purpose**: Platform management and oversight

**Features**:
- Total users (with active count)
- MSMEs count
- Affiliates count
- Platform revenue (ZMW)

**Sections**:
1. **Key Metrics** (4 metric cards)
2. **System Health** (API, DB, uptime, storage)
3. **Pending Approvals** (MSME apps, affiliate verifications)
4. **Recent Activity** (event timeline)
5. **Revenue Trends** (7-day chart)
6. **Quick Actions** (admin tools)

**API Endpoints**:
```typescript
GET /admin/stats
Response: {
  totalUsers: number,
  totalMSMEs: number,
  totalAffiliates: number,
  platformRevenue: number,
  activeUsers: number,
  systemHealth: number,
  pendingApprovals: number
}

GET /admin/users
Response: User[]

GET /admin/approvals
Response: Approval[]

GET /admin/activity
Response: Activity[]
```

---

## Authentication Flow

### Token Management
1. Login → Receive `accessToken` + `refreshToken`
2. Store in localStorage: `ntheemba_access_token`, `ntheemba_refresh_token`
3. Attach `Authorization: Bearer {accessToken}` to all requests
4. On 401 → Auto-refresh using `POST /auth/refresh`
5. On refresh failure → Clear tokens, dispatch `ntheemba:auth-expired` event
6. AuthContext listens to event → Update state → Redirect to login

### Demo Mode
- Click "Demo as [Role]" → Set mock token → Navigate to dashboard
- No backend required for exploration
- Mock data displayed in all views

---

## Data Flow

### Axios Interceptor Architecture
```
Request → Add Bearer token → Send to API
Response → Success → Return data
Response → 401 Error → 
  → If not retried → Refresh token
  → If refresh succeeds → Retry original request
  → If refresh fails → Clear auth, emit event
```

### State Management
- No global state (kept minimal)
- useState for local component state
- TanStack Query for server state (future enhancement)
- AuthContext for authentication state

---

## Styling & Design

### Design System
- **Colors**: HSL-based theme with CSS variables
- **Typography**: System font stack
- **Components**: shadcn/ui (Radix primitives + Tailwind)
- **Layout**: Responsive grid (1/2/4 columns)
- **Animations**: Tailwind animate plugin

### Responsive Breakpoints
- Mobile: < 640px (1 column)
- Tablet: 640-1024px (2 columns)
- Desktop: > 1024px (4 columns)

### Component Variants
- **Buttons**: default, destructive, outline, secondary, ghost, link
- **Badges**: default, secondary, destructive, outline
- **Cards**: Consistent padding, shadow, hover effects

---

## Alignment with Backend Requirements

### ✅ Implemented (Frontend Ready)
1. Auth with token refresh
2. Dashboard metrics display
3. Product/campaign UI structure
4. Earnings/payout UI
5. Analytics visualizations
6. Responsive layouts
7. Error handling

### ❌ Missing Backend Endpoints

#### Priority 1 (Core Features)
1. **Orders & Order Items**
   - `GET /msme/orders` - Order list with items
   - `POST /msme/orders` - Create order
   - `GET /affiliate/conversions` - Track conversions

2. **Payments & Transactions**
   - `POST /payments/initiate` - Start payment
   - `POST /payments/webhook` - Handle provider callback
   - `GET /payments/history` - Transaction list

3. **Affiliate Payouts**
   - `GET /affiliate/earnings` - Earnings history
   - `POST /affiliate/payout` - Request payout
   - `GET /affiliate/payouts` - Payout status

#### Priority 2 (Analytics)
4. **Click Events**
   - `POST /affiliate/clicks` - Record click
   - `GET /affiliate/clicks/stats` - Click analytics

5. **Inventory Management**
   - `GET /msme/inventory` - Stock levels
   - `POST /msme/inventory/adjust` - Update stock
   - `GET /msme/inventory/alerts` - Low stock alerts

#### Priority 3 (Extended Features)
6. **Service Bookings**
   - `POST /msme/services/book` - Create booking
   - `GET /msme/bookings` - Booking list

7. **Reviews**
   - `POST /products/:id/reviews` - Add review
   - `GET /products/:id/reviews` - Review list

8. **Audit Logs**
   - `GET /admin/audit` - Audit trail
   - Internal: Log all important actions

---

## API Contract Checklist

### Auth Endpoints
- [x] `POST /auth/login` - Returns accessToken, refreshToken, role
- [x] `POST /auth/refresh` - Returns new accessToken
- [ ] `POST /auth/register` - User registration
- [ ] `POST /auth/verify-otp` - OTP verification
- [ ] `POST /auth/logout` - Logout

### Affiliate Endpoints
- [ ] `GET /affiliate/stats` - Dashboard metrics
- [ ] `GET /affiliate/campaigns` - Campaign list
- [ ] `GET /affiliate/earnings` - Earnings history
- [ ] `POST /affiliate/payout` - Request payout
- [ ] `POST /affiliate/clicks` - Record click event
- [ ] `GET /affiliate/links/:campaignId` - Generate link

### MSME Endpoints
- [ ] `GET /msme/stats` - Dashboard metrics
- [ ] `GET /msme/products` - Product list
- [ ] `POST /msme/products` - Add product
- [ ] `PUT /msme/products/:id` - Update product
- [ ] `DELETE /msme/products/:id` - Delete product
- [ ] `GET /msme/orders` - Order list
- [ ] `GET /msme/inventory` - Inventory status

### Admin Endpoints
- [ ] `GET /admin/stats` - Platform metrics
- [ ] `GET /admin/users` - User list
- [ ] `GET /admin/approvals` - Pending approvals
- [ ] `POST /admin/approve/:id` - Approve item
- [ ] `GET /admin/activity` - Recent activity

---

## Field Name Conventions

### Agreement Needed (from alignment doc)

1. **Price Fields**
   - Frontend: `priceZMW` (integer cents)
   - Backend: TBD - `price` (decimal) or `price_cents` (integer)?

2. **Timestamps**
   - Frontend: ISO 8601 strings
   - Backend: TBD - ISO 8601 or Unix timestamps?

3. **IDs**
   - Frontend: string UUIDs
   - Backend: TBD - UUID or integer?

4. **Currency**
   - Always ZMW (Zambian Kwacha)
   - Display: "ZMW 12,340"
   - API: numeric value only

---

## Next Steps

### Phase 1: Backend API Implementation
1. Implement auth endpoints (`/auth/*`)
2. Implement dashboard stats endpoints
3. Add OpenAPI/Swagger documentation
4. Deploy to staging (port 8980)

### Phase 2: Core Features
1. Products CRUD endpoints
2. Orders & order items
3. Payment integration (MTN/Airtel/Zamtel)
4. Click tracking endpoint

### Phase 3: Advanced Features
1. Affiliate payout workflows
2. Inventory management
3. Service bookings
4. Reviews system

### Phase 4: Testing
1. E2E tests for auth flow
2. Integration tests for APIs
3. Load testing for performance
4. Security audit

---

## Running the App

### Development
```bash
cd services/frontend/web-services/mini_dashboards
npm install
npm run dev
# App runs on http://localhost:3000
```

### Production Build
```bash
npm run build
# Output in dist/
```

### Environment Setup
```bash
# Create .env file
echo "VITE_API_URL=http://localhost:8980" > .env
```

---

## File Structure
```
mini_dashboards/
├── src/
│   ├── components/
│   │   └── ui/               # shadcn/ui components
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── badge.tsx
│   │       └── progress.tsx
│   ├── lib/
│   │   ├── api.ts           # Axios client
│   │   ├── auth.ts          # Token helpers
│   │   ├── authContext.tsx  # Auth provider
│   │   └── utils.ts         # Utilities
│   ├── pages/
│   │   ├── Landing.tsx      # Marketing page
│   │   ├── Login.tsx        # Auth page
│   │   ├── AffiliateDashboard.tsx
│   │   ├── MSMEDashboard.tsx
│   │   └── AdminDashboard.tsx
│   ├── App.tsx              # Router setup
│   ├── main.tsx             # Entry point
│   └── index.css            # Tailwind styles
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── README.md
```

---

## Summary

✅ **Complete**: Mini dashboards app with all pages, routing, auth, and API integration
✅ **Design**: Follows existing dashboards design language
✅ **API Ready**: Axios client configured for port 8980 with token refresh
✅ **Demo Mode**: Can explore without backend
✅ **Responsive**: Mobile-first design with breakpoints
✅ **TypeScript**: Full type safety

❌ **Next**: Backend team needs to implement the API endpoints listed above
