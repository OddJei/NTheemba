# Complete Pages and Endpoints Documentation

## Table of Contents

1. [Frontend Pages](#frontend-pages)
   - [MSME Dashboard Pages](#msme-dashboard-pages)
   - [Affiliate Dashboard Pages](#affiliate-dashboard-pages)
   - [Landing Pages](#landing-pages)
2. [Backend Services](#backend-services)
   - [Order-Delivery Service](#order-delivery-service)
   - [Affiliate-Engine Service](#affiliate-engine-service)
   - [Payment-Revenue Service](#payment-revenue-service)
   - [Cart Service](#cart-service)
   - [Catalog-Inventory Service](#catalog-inventory-service)
   - [Notification Service](#notification-service)
   - [Bot-Session Service](#bot-session-service)
   - [Audit Service](#audit-service)
   - [MSME-Engine Service](#msme-engine-service)

---

## Frontend Pages

### MSME Dashboard Pages

#### 1. Dashboard (`/msme/dashboard`)

**Purpose:** Main dashboard for MSME business owners

**Page Content:**

- Today's sales statistics
- New messages count
- Low stock items alert
- Active products count
- Recent orders list
- Quick actions (Add Product, View Orders)
- Sales trends chart
- Notifications/Alerts

**Endpoints Called:**

- `GET /api/orders/pending?business_id={id}` - Get pending orders
- `GET /api/products?business_id={id}` - Get products list
- `GET /api/insights/sales?business_id={id}` - Get sales statistics
- `GET /api/inventory/low-stock?business_id={id}` - Get low stock items

---

#### 2. Products (`/msme/products`)

**Purpose:** Product catalog and inventory management

**Page Content:**

- Product listing (grid/list view)
- Add new product form
- Edit product capabilities
- Product variants management
- Inventory levels
- Product images upload
- Category management
- Pricing information

**Endpoints Called:**

- `GET /catalog/business/{business_id}/products` - List all products
- `POST /catalog/product` - Create new product
- `PUT /catalog/product/{product_id}` - Update product
- `DELETE /catalog/product/{product_id}` - Delete product
- `POST /catalog/variant` - Add product variant
- `PUT /inventory/update` - Update inventory levels
- `POST /uploads/presigned` - Get upload URL for images
- `GET /catalog/categories?business_id={id}` - Get categories

---

#### 3. Insights (`/msme/insights`)

**Purpose:** Business analytics and performance metrics

**Page Content:**

- Revenue trends chart
- Sales by product
- Customer analytics
- Order completion rates
- Peak sales times
- Geographic distribution
- Conversion metrics
- Period comparison tools

**Endpoints Called:**

- `GET /api/insights/revenue?business_id={id}&period={period}` - Revenue analytics
- `GET /api/insights/products?business_id={id}` - Product performance
- `GET /api/orders/analytics?business_id={id}` - Order analytics
- `GET /api/insights/customers?business_id={id}` - Customer insights

---

#### 4. Campaigns (`/msme/campaigns`)

**Purpose:** Marketing campaign management

**Page Content:**

- Active campaigns list
- Create new campaign
- Campaign performance metrics
- Target audience settings
- Budget tracking
- Campaign templates

**Endpoints Called:**

- `GET /api/campaigns?business_id={id}` - List campaigns
- `POST /api/campaigns` - Create campaign
- `PUT /api/campaigns/{campaign_id}` - Update campaign
- `GET /api/campaigns/{campaign_id}/metrics` - Campaign analytics

---

#### 5. Branding (`/msme/branding`)

**Purpose:** Business branding and profile customization

**Page Content:**

- Business logo upload
- Brand colors
- Business information
- Store description
- Contact details
- Social media links
- WhatsApp business number

**Endpoints Called:**

- `GET /api/business/{business_id}` - Get business profile
- `PUT /api/business/{business_id}` - Update business profile
- `POST /uploads/presigned` - Upload branding assets
- `PUT /api/business/{business_id}/branding` - Update branding

---

#### 6. Subscription (`/msme/subscription`)

**Purpose:** Manage MSME subscription and billing

**Page Content:**

- Current plan details
- Billing history
- Payment methods
- Upgrade/downgrade options
- Feature usage stats
- Renewal date
- Invoice downloads

**Endpoints Called:**

- `GET /api/subscriptions/{business_id}` - Get subscription details
- `POST /api/subscriptions/upgrade` - Upgrade plan
- `GET /api/subscriptions/invoices` - Get billing history
- `POST /api/subscriptions/payment-method` - Update payment method

---

#### 7. Subscription Plans (`/msme/subscription-plans`)

**Purpose:** View and select MSME subscription tiers

**Page Content:**

- Available plans (Free, Starter, Professional, Enterprise)
- Features comparison
- Pricing details
- Transaction fee rates
- Plan benefits
- Trial information
- Select/Upgrade buttons

**Endpoints Called:**

- `GET /api/subscription-plans` - Get available plans
- `POST /api/subscriptions/select` - Select a plan
- `POST /api/payment/subscription` - Process subscription payment

---

### Affiliate Dashboard Pages

#### 1. Dashboard (`/affiliate/dashboard`)

**Purpose:** Main affiliate dashboard

**Page Content:**

- Total earnings (today, this month, all-time)
- Click statistics
- Conversion metrics
- Active campaigns count
- Recent activities feed
- Upcoming payouts
- Performance trends
- Tier status and progress
- Quick actions

**Endpoints Called:**

- `GET /affiliates/{affiliate_id}` - Get affiliate profile
- `GET /affiliates/{affiliate_id}/earnings` - Get earnings data
- `GET /affiliates/{affiliate_id}/clicks` - Get click statistics
- `GET /affiliates/{affiliate_id}/attributions` - Get conversions
- `GET /events/affiliate/{affiliate_id}` - Get recent activities
- `GET /affiliates/{affiliate_id}/metrics` - Get performance metrics

---

#### 2. Link Generator (`/affiliate/link-generator`)

**Purpose:** Create and manage affiliate links

**Page Content:**

- Product selector
- Campaign selector
- Custom link generator
- QR code generator
- Short link creation
- Link preview
- Copy to clipboard
- Share buttons (WhatsApp, Facebook, Twitter)
- Link performance tracking

**Endpoints Called:**

- `POST /affiliates/{affiliate_id}/links` - Create new link
- `GET /affiliates/{affiliate_id}/links` - List all links
- `GET /catalog/business/{business_id}/products` - Get products to promote
- `POST /track/click` - Track link clicks
- `GET /a/{affiliate_code}/resolve` - Resolve affiliate link

---

#### 3. Earnings (`/affiliate/earnings`)

**Purpose:** Detailed earnings and commission tracking

**Page Content:**

- Earnings summary (pending, confirmed, paid)
- Transaction history
- Commission breakdown by product/campaign
- Earnings chart (daily/weekly/monthly)
- Tier-based commission rates
- Pool allocation details
- Epoch performance
- Downloadable reports

**Endpoints Called:**

- `GET /affiliates/{affiliate_id}/earnings` - Get earnings details
- `GET /affiliates/{affiliate_id}/attributions` - Get attributed orders
- `GET /epoch/{epoch_id}/allocations?affiliate_id={id}` - Get pool allocations
- `GET /admin/epochs/{epoch_id}/debug-scores` - Get performance scores

---

#### 4. Payouts (`/affiliate/payouts`)

**Purpose:** Payout management and history

**Page Content:**

- Available balance
- Payout threshold
- Pending payouts
- Payout history
- Payment method settings
- Request payout button
- Transaction status
- Payment receipts

**Endpoints Called:**

- `GET /affiliates/{affiliate_id}/payouts` - Get payout history
- `POST /payouts/request` - Request payout
- `GET /callbacks/payments/payouts` - Payout status updates
- `PUT /affiliates/{affiliate_id}/payment-info` - Update payment details

---

#### 5. Campaigns (`/affiliate/campaigns`)

**Purpose:** View and manage promotional campaigns

**Page Content:**

- Available campaigns to join
- Active campaigns
- Campaign performance metrics
- Campaign details (products, commission rates, duration)
- Join/Leave campaign
- Campaign materials (banners, copy)

**Endpoints Called:**

- `GET /api/campaigns?type=affiliate` - List available campaigns
- `POST /api/campaigns/{campaign_id}/join` - Join campaign
- `GET /affiliates/{affiliate_id}/campaigns` - Get active campaigns
- `GET /api/campaigns/{campaign_id}/materials` - Get marketing materials

---

#### 6. Content (`/affiliate/content`)

**Purpose:** Marketing content and promotional materials

**Page Content:**

- Pre-made promotional content
- Product images and descriptions
- Social media templates
- WhatsApp message templates
- Banner images
- Video content
- Content guidelines
- Download assets

**Endpoints Called:**

- `GET /api/content/promotional` - Get promotional content
- `GET /catalog/business/{business_id}/products` - Get product details
- `GET /uploads/{asset_id}` - Download marketing assets

---

#### 7. Leaderboards (`/affiliate/leaderboards`)

**Purpose:** Competitive leaderboards and rankings

**Page Content:**

- Top affiliates by earnings
- Top by clicks
- Top by conversions
- Weekly/monthly/all-time rankings
- Your rank position
- Tier-based leaderboards
- Achievement badges
- Community challenges

**Endpoints Called:**

- `GET /api/leaderboards/affiliates` - Get leaderboard data
- `GET /affiliates/{affiliate_id}/rank` - Get user rank
- `GET /api/leaderboards/challenges` - Get active challenges

---

#### 8. Notifications (`/affiliate/notifications`)

**Purpose:** Activity notifications and alerts

**Page Content:**

- Real-time notifications feed
- New click alerts
- Conversion notifications
- Payout updates
- Campaign announcements
- System notifications
- Mark as read/unread
- Notification preferences

**Endpoints Called:**

- `GET /notifications/stream` - SSE stream for real-time notifications
- `GET /api/notifications?user_id={id}` - Get notification history
- `PUT /api/notifications/{notification_id}/read` - Mark as read
- `PUT /api/notifications/preferences` - Update preferences

---

#### 9. Profile (`/affiliate/profile`)

**Purpose:** Affiliate profile management

**Page Content:**

- Personal information
- Contact details
- WhatsApp number
- Profile picture
- Bio/Description
- Social media links
- Referral code
- Account status

**Endpoints Called:**

- `GET /affiliates/{affiliate_id}` - Get profile
- `PUT /affiliates/{affiliate_id}` - Update profile
- `POST /uploads/presigned` - Upload profile picture
- `GET /token/resolve` - Resolve affiliate token

---

#### 10. Security (`/affiliate/security`)

**Purpose:** Account security and authentication

**Page Content:**

- Change password
- Two-factor authentication
- Active sessions
- Login history
- API keys (if applicable)
- Security settings
- Privacy preferences

**Endpoints Called:**

- `PUT /auth/change-password` - Update password
- `POST /auth/2fa/enable` - Enable 2FA
- `GET /auth/sessions` - Get active sessions
- `DELETE /auth/sessions/{session_id}` - Revoke session

---

#### 11. Feedback (`/affiliate/feedback`)

**Purpose:** Provide feedback and support

**Page Content:**

- Feedback form
- Bug reporting
- Feature requests
- Support tickets
- FAQ section
- Contact support
- Feedback history

**Endpoints Called:**

- `POST /api/feedback` - Submit feedback
- `GET /api/feedback?user_id={id}` - Get feedback history
- `POST /api/support/ticket` - Create support ticket
- `GET /api/support/tickets` - View tickets

---

#### 12. Subscription (`/affiliate/subscription`)

**Purpose:** Manage affiliate subscription

**Page Content:**

- Current tier (Basic, Pro, Elite)
- Ubuntu community status
- Features unlocked
- Subscription billing
- Upgrade options
- Benefits overview

**Endpoints Called:**

- `GET /api/subscriptions/affiliate/{affiliate_id}` - Get subscription
- `POST /api/subscriptions/affiliate/upgrade` - Upgrade tier
- `GET /api/subscriptions/features` - Get feature access

---

#### 13. Subscription Plans (`/affiliate/subscription-plans`)

**Purpose:** View and select affiliate tiers

**Page Content:**

- Basic, Pro, Elite tier comparison
- Ubuntu community benefits
- Commission rates by tier
- Feature comparison
- Pricing details
- Select/Upgrade buttons

**Endpoints Called:**

- `GET /api/subscription-plans/affiliate` - Get available tiers
- `POST /api/subscriptions/affiliate/select` - Select tier
- `GET /api/tiers/settings` - Get tier settings

---

### Landing Pages

#### 1. Home/Index (`/`)

**Purpose:** Main landing page

**Page Content:**

- Hero section
- Feature highlights
- Testimonials
- Call-to-action buttons
- Platform overview
- Login/Signup links

**Endpoints Called:**

- None (static content)
- `POST /auth/register` - User registration (from signup form)

---

#### 2. Login (`/login`)

**Purpose:** User authentication

**Page Content:**

- Login form (identifier + password)
- Role selection (MSME, Affiliate, Admin)
- Forgot password link
- Register link
- Social login options

**Endpoints Called:**

- `POST /auth/login` - Authenticate user
- `POST /auth/forgot-password` - Password reset request

---

#### 3. Ubuntu Community (`/ubuntu-community`)

**Purpose:** Ubuntu community membership page

**Page Content:**

- Community overview
- Benefits of joining
- Membership tiers
- Success stories
- Join community form
- Community guidelines

**Endpoints Called:**

- `POST /api/ubuntu/join` - Join Ubuntu community
- `GET /api/ubuntu/members` - View community members (if applicable)

---

#### 4. Subscription Plans (`/subscription-plans`)

**Purpose:** General subscription information

**Page Content:**

- All subscription types
- MSME plans
- Affiliate tiers
- Pricing comparison
- FAQ
- Contact sales

**Endpoints Called:**

- `GET /api/subscription-plans/all` - Get all plans

---

## Backend Services

### Order-Delivery Service

**Port:** 8560
**Base URL:** `http://127.0.0.1:8560`

#### Health & Metrics (Order-Delivery)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Orders

- `POST /orders/create` - Create new order
  - Body: `{ business_id, user_phone, delivery_method, total_amount, currency, metadata }`
  - Returns: Order object with status "pending_payment"
  
- `GET /orders/pending` - List pending orders for business
  - Query: `business_id`, `limit`, `offset`
  - Returns: List of pending orders
  
- `GET /orders/{order_id}` - Get order details
  - Returns: Full order object
  
- `POST /orders/{order_id}/initiate_payment` - Initiate payment via pawaPay
  - Body: `{ phoneNumber, provider, currency }`
  - Returns: Payment initiation response
  
- `POST /orders/{order_id}/mark_paid` - Mark order as paid (internal)
  - Called by payment-revenue service
  - Returns: Updated order
  
- `POST /orders/{order_id}/deny` - Business denies order
  - Body: `{ reason, initiate_refund }`
  - Returns: Updated order with "denied" status
  
- `PUT /orders/{order_id}/delivery_location` - Set delivery location
  - Body: `{ delivery_location }`
  - Returns: Updated order with delivery fee
  
- `PUT /orders/{order_id}/payment_method` - Update payment phone
  - Body: `{ phone_number }`
  - Returns: Updated order

#### Delivery

- `POST /delivery/initiate/{order_id}` - Initiate delivery
  - Returns: Delivery object with 6-digit code
  
- `POST /delivery/{delivery_id}/confirm` - Confirm delivery
  - Body: `{ code }`
  - Returns: Confirmed delivery object
  
- `GET /delivery/{delivery_id}` - Get delivery details
  - Returns: Delivery object

#### Outbox (Internal)

- `GET /outbox/pending` - Get unprocessed events
  - Header: `X-Internal-Secret`
  - Query: `batch_size`
  
- `POST /outbox/ack` - Acknowledge processed events
  - Header: `X-Internal-Secret`
  - Body: `{ ids: [] }`

---

### Affiliate-Engine Service

**Port:** 8510
**Base URL:** `http://127.0.0.1:8510`

#### Health Check (Affiliate-Engine)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Affiliates

- `POST /affiliates` - Create affiliate
  - Body: `{ whatsapp_number, name, business_id, pool_pct, tier }`
  - Returns: Affiliate object
  
- `GET /affiliates/{affiliate_id}` - Get affiliate details
  - Returns: Full affiliate profile
  
- `GET /affiliates` - List all affiliates
  - Returns: Array of affiliates

#### Links

- `POST /affiliates/{affiliate_id}/links` - Create affiliate link
  - Body: `{ target_url, campaign }`
  - Returns: Generated link with code
  
- `GET /affiliates/{affiliate_id}/links` - List affiliate links
  - Returns: Array of links
  
- `GET /a/{affiliate_code}/resolve` - Resolve affiliate link
  - Returns: Target URL and affiliate info

#### Tracking

- `POST /track/click` - Track link click
  - Body: `{ affiliate_code, user_agent, ip_address }`
  - Returns: Click record
  
- `POST /attribute/order` - Attribute order to affiliate
  - Body: `{ order_id, affiliate_code, amount }`
  - Returns: Attribution record
  
- `GET /affiliates/{affiliate_id}/clicks` - Get click history
  - Returns: Array of clicks
  
- `GET /affiliates/{affiliate_id}/attributions` - Get attributions
  - Returns: Array of attributed orders

#### Events

- `POST /events/order-created` - Process order created event
  - Body: Order event payload
  - Returns: Attribution confirmation
  
- `POST /events/order/delivered` - Process order delivered event
  - Body: Delivery event payload
  - Returns: Success confirmation
  
- `GET /events/affiliate/{affiliate_id}` - Get affiliate events
  - Returns: Event history

#### Notifications (Affiliate-Engine)

- `GET /notifications/stream` - SSE stream for real-time notifications
  - Returns: Server-Sent Events stream
  
- `POST /events/payment-success` - Payment success event
  - Body: Payment event payload

#### Token & Resolution

- `POST /token/resolve` - Resolve affiliate token
  - Body: `{ token }`
  - Returns: Affiliate info

#### Callbacks

- `POST /callbacks/payments/deposits` - Deposit callback
- `POST /callbacks/payments/payouts` - Payout callback
- `POST /callbacks/payments/refunds` - Refund callback

#### Admin

- `GET /admin/epochs/{epoch_id}/debug-scores` - Debug epoch scores
  - Returns: Detailed scoring breakdown

---

### Payment-Revenue Service

**Port:** 8590
**Base URL:** `http://127.0.0.1:8590`

#### Service Health (Payment-Revenue)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Deposits (Payments)

- `POST /pawapay/deposits/initiate` - Initiate deposit
  - Body: `{ order_id, phoneNumber, amount, currency, provider }`
  - Returns: PawaPay transaction details
  
- `GET /pawapay/deposits/{deposit_id}` - Get deposit status
  - Returns: Transaction status
  
- `POST /callbacks/pawapay/deposits` - PawaPay deposit webhook
  - Body: PawaPay callback payload

#### Payouts

- `POST /pawapay/payouts/initiate` - Initiate payout
  - Body: `{ correspondent, phoneNumber, amount, currency }`
  - Returns: Payout transaction details
  
- `GET /pawapay/payouts/{payout_id}` - Get payout status
  - Returns: Payout status
  
- `POST /callbacks/pawapay/payouts` - PawaPay payout webhook
  - Body: PawaPay callback payload
  
- `POST /payout/batch` - Batch payout processing
  - Body: `{ epoch_id, affiliate_ids }`
  - Returns: Batch processing confirmation

#### Refunds

- `POST /pawapay/refunds/initiate` - Initiate refund
  - Body: `{ depositId, amount, currency, reason }`
  - Returns: Refund transaction details
  
- `GET /pawapay/refunds/{refund_id}` - Get refund status
  - Returns: Refund status
  
- `POST /callbacks/pawapay/refunds` - PawaPay refund webhook
  - Body: PawaPay callback payload
  
- `POST /refunds/request` - Request refund
  - Body: `{ order_id, reason }`
  - Returns: Refund details

#### Settlements & Payouts

- `GET /settlements/{order_id}` - Get settlement details
  - Returns: Settlement breakdown
  
- `GET /payouts/{order_id}` - Get payouts for order
  - Returns: Array of payouts

#### MSME Payouts

- `POST /msme/payouts/initiate` - Initiate MSME payout
  - Body: `{ order_id, business_id, amount }`
  - Returns: Payout details
  
- `GET /msme/payouts/{order_id}` - Get MSME payout
  - Returns: Payout status
  
- `POST /events/msme-payout-initiate` - MSME payout event
  - Body: Event payload

#### Revenue Analytics

- `GET /admin/gross-revenue` - Get gross revenue
  - Returns: Revenue summary
  
- `GET /epoch/{epoch_id}/gross-revenue` - Get epoch revenue
  - Returns: Epoch-specific revenue
  
- `GET /admin/platform-balance` - Get platform balance
  - Returns: Platform financial summary

#### Jobs (Internal)

- `POST /jobs/pawapay/reconcile` - Reconcile PawaPay transactions
- `POST /jobs/outbox/flush` - Flush outbox events

---

### Cart Service

**Port:** 8580
**Base URL:** `http://127.0.0.1:8580`

#### Service Health (Cart)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Cart Operations

- `POST /cart` - Create cart
  - Body: `{ user_id, business_id }`
  - Returns: Cart object
  
- `GET /cart/{cart_id}` - Get cart
  - Returns: Cart with items
  
- `POST /cart/{cart_id}/item` - Add item to cart
  - Body: `{ product_id, quantity, variant_id }`
  - Returns: Updated cart
  
- `PUT /cart/{cart_id}/item/{item_id}` - Update cart item
  - Body: `{ quantity }`
  - Returns: Updated cart
  
- `DELETE /cart/{cart_id}/item/{item_id}` - Remove item from cart
  - Returns: Updated cart
  
- `POST /cart/{cart_id}/checkout` - Checkout cart
  - Body: `{ delivery_method, payment_method }`
  - Returns: Order ID and checkout details
  
- `DELETE /cart/{cart_id}` - Clear/delete cart
  - Returns: Success confirmation

---

### Catalog-Inventory Service

**Port:** 8550
**Base URL:** `http://127.0.0.1:8550`

#### Service Health (Catalog-Inventory)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Categories

- `POST /catalog/category` - Create category
  - Body: `{ business_id, name, description, parent_id }`
  - Returns: Category object
  
- `GET /catalog/categories` - List categories
  - Query: `business_id`
  - Returns: Array of categories
  
- `PUT /catalog/category/{category_id}` - Update category
  - Body: Category fields
  - Returns: Updated category
  
- `DELETE /catalog/category/{category_id}` - Delete category
  - Returns: Success confirmation

#### Products

- `POST /catalog/product` - Create product
  - Body: `{ business_id, name, description, price, category_id, images }`
  - Returns: Product object
  
- `GET /catalog/product/{product_id}` - Get product
  - Returns: Full product details
  
- `GET /catalog/business/{business_id}/products` - List business products
  - Returns: Array of products
  
- `PUT /catalog/product/{product_id}` - Update product
  - Body: Product fields
  - Returns: Updated product
  
- `DELETE /catalog/product/{product_id}` - Delete product
  - Returns: Success confirmation

#### Variants

- `POST /catalog/variant` - Create product variant
  - Body: `{ product_id, name, price, sku }`
  - Returns: Variant object
  
- `GET /catalog/product/{product_id}/variants` - List variants
  - Returns: Array of variants
  
- `PUT /catalog/variant/{variant_id}` - Update variant
  - Body: Variant fields
  - Returns: Updated variant
  
- `DELETE /catalog/variant/{variant_id}` - Delete variant
  - Returns: Success confirmation

#### Inventory

- `GET /inventory/{product_id}` - Get inventory levels
  - Returns: Stock information
  
- `POST /inventory/update` - Update inventory
  - Body: `{ product_id, variant_id, quantity, operation }`
  - Returns: Updated inventory
  
- `GET /inventory/low-stock` - Get low stock items
  - Query: `business_id`, `threshold`
  - Returns: Array of low stock products

#### Media Uploads

- `POST /uploads/presigned` - Get presigned upload URL
  - Body: `{ filename, content_type }`
  - Returns: Presigned URL for S3/WebDAV upload
  
- `POST /uploads/batch` - Batch upload handling
  - Body: Multiple file info
  - Returns: Array of upload URLs

#### Catalog Export

- `GET /catalog/business/{business_id}/export` - Export catalog
  - Returns: Full business catalog

---

### Notification Service

**Port:** 8570
**Base URL:** `http://127.0.0.1:8570`

#### Service Health (Notifications)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Notifications (Notification Service)

- `POST /notification/send` - Send notification
  - Body: `{ channel, user_id, business_id, template, payload }`
  - Channels: `whatsapp`, `sms`, `in_app`, `email`
  - Returns: Notification ID
  
- `GET /notifications` - List user notifications
  - Query: `user_id`, `business_id`
  - Returns: Array of notifications
  
- `PUT /notifications/{notification_id}/read` - Mark as read
  - Returns: Updated notification
  
- `GET /notifications/unread-count` - Get unread count
  - Query: `user_id`
  - Returns: Count

#### Templates

- `GET /notification/templates` - List templates
  - Returns: Available templates
  
- `POST /notification/template` - Create template
  - Body: Template definition
  - Returns: Template ID

---

### Bot-Session Service

**Port:** 8595
**Base URL:** `http://127.0.0.1:8595`

#### Service Health (Bot-Session)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Sessions

- `POST /session/create` - Create bot session
  - Body: `{ user_phone, business_id }`
  - Returns: Session object
  
- `GET /session/{session_id}` - Get session
  - Returns: Session details
  
- `GET /session/{session_id}/cycles` - Get session cycles
  - Returns: Array of conversation cycles with affiliate tracking

#### Messages

- `POST /session/{session_id}/message` - Send message
  - Body: `{ message, user_phone }`
  - Returns: Bot response
  
- `GET /session/{session_id}/messages` - Get message history
  - Returns: Array of messages

---

### Audit Service

**Port:** 8290
**Base URL:** `http://127.0.0.1:8290`

#### Service Health (Audit)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Audit Logs

- `POST /audit/log` - Submit audit log
  - Body: `{ service, event_type, payload, actor_id, entity_type, entity_id, metadata }`
  - Returns: Log ID
  
- `GET /audit/logs` - Query audit logs
  - Query: `service`, `event_type`, `entity_id`, `start_date`, `end_date`
  - Returns: Array of audit records
  
- `GET /audit/entity/{entity_type}/{entity_id}` - Get entity audit trail
  - Returns: Entity's audit history

---

### MSME-Engine Service

**Port:** 8500
**Base URL:** `http://127.0.0.1:8500`

#### Service Health (MSME-Engine)

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

#### Authentication

- `POST /auth/login` - User login
  - Body: `{ identifier, password }`
  - Returns: JWT access token
  
- `POST /auth/register` - User registration
  - Body: `{ identifier, password, role, business_id }`
  - Returns: User object
  
- `POST /auth/refresh` - Refresh token
  - Body: `{ refresh_token }`
  - Returns: New access token
  
- `POST /auth/logout` - Logout
  - Returns: Success confirmation

#### Business

- `POST /business` - Create business
  - Body: Business details
  - Returns: Business object
  
- `GET /business/{business_id}` - Get business
  - Returns: Business profile
  
- `PUT /business/{business_id}` - Update business
  - Body: Business fields
  - Returns: Updated business
  
- `GET /business/{business_id}/entitlements` - Get entitlements
  - Returns: Subscription features and transaction fees
  
- `GET /businesses/{business_id}/delivery-locations` - Get delivery locations
  - Returns: Available delivery zones with fees

#### Subscriptions

- `GET /subscriptions/{business_id}` - Get subscription
  - Returns: Subscription details
  
- `POST /subscriptions/upgrade` - Upgrade subscription
  - Body: `{ plan_id }`
  - Returns: Updated subscription
  
- `GET /subscription-plans` - List plans
  - Returns: Available subscription plans

---

## Authentication Flow

### JWT Token Structure

```json
{
  "sub": "user_id",
  "role": "msme|affiliate|admin",
  "business_id": "uuid",
  "exp": 1234567890
}
```text

### Authentication Headers

```text

Authorization: Bearer {jwt_token}
X-Correlation-Id: {uuid} (optional, for request tracing)
X-Idempotency-Key: {key} (optional, for idempotent operations)
X-Business-Id: {uuid} (optional, for multi-tenant access)

```

---

## Error Response Format

All endpoints return errors in this format:

```json
{
  "detail": "error_code_or_message"
}
```

### Common HTTP Status Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Missing/invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Idempotency conflict or business rule violation
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error
- `502 Bad Gateway` - Upstream service unavailable

---

## Data Flow Examples

### 1. Complete Order Flow (with Affiliate)

```
1. User clicks affiliate link
   → POST /track/click (affiliate-engine)
   
2. User adds products to cart
   → POST /cart (cart service)
   → POST /cart/{id}/item (cart service)
   
3. User checks out
   → POST /cart/{id}/checkout (cart service)
   → POST /orders/create (order-delivery)
   → Outbox event created
   
4. Background dispatcher processes affiliate attribution
   → POST /events/order-created (affiliate-engine)
   
5. User initiates payment
   → POST /orders/{id}/initiate_payment (order-delivery)
   → POST /pawapay/deposits/initiate (payment-revenue)
   
6. PawaPay processes payment
   → POST /callbacks/pawapay/deposits (payment-revenue)
   → POST /orders/{id}/mark_paid (order-delivery)
   
7. Business initiates delivery
   → POST /delivery/initiate/{order_id} (order-delivery)
   → POST /notification/send (notification service)
   
8. Customer confirms delivery
   → POST /delivery/{id}/confirm (order-delivery)
   → Outbox event created
   
9. Background dispatcher finalizes affiliate attribution
   → POST /events/order/delivered (affiliate-engine)
   
10. System calculates payouts
    → POST /payout/batch (payment-revenue)
    → POST /pawapay/payouts/initiate (payment-revenue)
```

### 2. Product Management Flow

```
1. MSME creates category
   → POST /catalog/category (catalog-inventory)
   
2. MSME uploads product images
   → POST /uploads/presigned (catalog-inventory)
   → PUT {presigned_url} (direct to storage)
   
3. MSME creates product
   → POST /catalog/product (catalog-inventory)
   → Outbox event created
   
4. MSME adds variants
   → POST /catalog/variant (catalog-inventory)
   
5. MSME sets inventory levels
   → POST /inventory/update (catalog-inventory)
```

---

## Environment Configuration

### Required Environment Variables

#### All Services

- `DATABASE_URL` - PostgreSQL connection string
- `PG_SCHEMA` - Database schema name
- `JWT_SECRET` - JWT signing secret
- `INTERNAL_SERVICE_SECRET` - Internal service authentication

#### Order-Delivery

- `MSME_BASE_URL` - <http://127.0.0.1:8500>
- `PAYMENT_REVENUE_BASE_URL` - <http://127.0.0.1:8590>
- `AFFILIATE_ENGINE_BASE_URL` - <http://127.0.0.1:8510>
- `NOTIFICATION_BASE_URL` - <http://127.0.0.1:8570>
- `BOT_SESSION_BASE_URL` - <http://127.0.0.1:8595>
- `AUDIT_SERVICE_URL` - <http://127.0.0.1:8290>
- `OUTBOX_DISPATCH_ENABLED` - true
- `OUTBOX_DISPATCH_INTERVAL_SECONDS` - 2.0
- `OUTBOX_DISPATCH_BATCH_SIZE` - 50

#### Payment-Revenue

- `PAWAPAY_API_KEY` - PawaPay API key
- `PAWAPAY_BASE_URL` - PawaPay API URL
- `PAWAPAY_WEBHOOK_SECRET` - Webhook signature secret
- `AFFILIATE_COMMISSION_SHARE_OF_PLATFORM_FEE` - Commission percentage

---

## WebSocket/SSE Endpoints

### Real-time Notifications (Affiliate Dashboard)

```javascript
const eventSource = new EventSource(
  'http://127.0.0.1:8510/notifications/stream?affiliate_id={id}'
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle: clicks, conversions, payouts, etc.
};
```

---

## Rate Limiting

Most endpoints support rate limiting (implementation varies by service):

- Default: 100 requests per minute per user
- Burst: 200 requests per minute
- Headers returned:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

---

## Pagination

List endpoints support pagination:

```
GET /endpoint?limit=50&offset=0
```

Response includes:

```json
{
  "items": [...],
  "total": 1234,
  "limit": 50,
  "offset": 0
}
```

---

## Search & Filtering

Many GET endpoints support filtering:

```
GET /orders/pending?business_id={id}&status=pending_payment&limit=20
```

---

## Documentation Maintenance

**Last Updated:** February 16, 2026

**Services Documented:**

- ✅ Order-Delivery (8560)
- ✅ Affiliate-Engine (8510)
- ✅ Payment-Revenue (8590)
- ✅ Cart (8580)
- ✅ Catalog-Inventory (8550)
- ✅ Notification (8570)
- ✅ Bot-Session (8595)
- ✅ Audit (8290)
- ✅ MSME-Engine (8500)

**Frontend Pages Documented:**

- ✅ MSME Dashboard (7 pages)
- ✅ Affiliate Dashboard (13 pages)
- ✅ Landing Pages (4 pages)

---

## Support & Resources

- **API Documentation:** <http://127.0.0.1:{port}/docs> (Swagger UI)
- **API Reference:** <http://127.0.0.1:{port}/redoc> (ReDoc)
- **Monitoring:** <http://127.0.0.1:{port}/metrics> (Prometheus)
- **Health Check:** <http://127.0.0.1:{port}/health>

---

*This documentation is auto-generated based on the codebase structure. For specific implementation details, refer to the source code or API documentation endpoints.*
