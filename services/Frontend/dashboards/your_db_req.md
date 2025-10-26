# Database Requirements for NTheemba Platform

Based on the current frontend codebase analysis, here are the comprehensive database requirements for the NTheemba platform that supports both MSME businesses and Affiliate marketers.

## Core System Tables

### 1. Users & Authentication
```sql
-- Users table for authentication and basic info
users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('msme', 'affiliate', 'admin') NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    profile_image_url TEXT,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- User sessions for authentication management
user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 2. Subscription Plans & Billing
```sql
-- Subscription plans (Basic, Pro, Enterprise)
subscription_plans (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ZMW',
    billing_cycle ENUM('monthly', 'yearly') NOT NULL,
    features JSON, -- Store feature permissions
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- User subscriptions
user_subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES subscription_plans(id),
    status ENUM('active', 'cancelled', 'expired', 'trial') NOT NULL,
    trial_ends_at TIMESTAMP,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
```

## MSME Business Tables

### 3. Business Management
```sql
-- MSME business profiles
msme_businesses (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    business_name VARCHAR(255) NOT NULL,
    business_description TEXT,
    business_type VARCHAR(100),
    registration_number VARCHAR(100),
    tax_id VARCHAR(100),
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    website_url TEXT,
    logo_url TEXT,
    is_verified BOOLEAN DEFAULT false,
    business_health_score INT DEFAULT 0, -- 0-100 performance score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- Products/Services catalog
products (
    id UUID PRIMARY KEY,
    business_id UUID REFERENCES msme_businesses(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ZMW',
    stock_quantity INT DEFAULT 0,
    sku VARCHAR(100) UNIQUE,
    status ENUM('active', 'inactive', 'out_of_stock', 'low_stock') DEFAULT 'active',
    images JSON, -- Array of image URLs
    weight DECIMAL(8,2),
    dimensions JSON, -- {length, width, height}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- Product categories
product_categories (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_category_id UUID REFERENCES product_categories(id),
    is_active BOOLEAN DEFAULT true
)
```

### 4. Sales & Orders
```sql
-- Customer orders
orders (
    id UUID PRIMARY KEY,
    business_id UUID REFERENCES msme_businesses(id),
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_phone VARCHAR(20),
    total_amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ZMW',
    status ENUM('pending', 'confirmed', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
    payment_status ENUM('pending', 'paid', 'failed', 'refunded') DEFAULT 'pending',
    shipping_address TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- Order items
order_items (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id),
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL
)

-- Daily sales metrics for dashboard
daily_sales_metrics (
    id UUID PRIMARY KEY,
    business_id UUID REFERENCES msme_businesses(id),
    date DATE NOT NULL,
    total_sales DECIMAL(10,2) DEFAULT 0,
    total_orders INT DEFAULT 0,
    new_customers INT DEFAULT 0,
    average_order_value DECIMAL(10,2) DEFAULT 0,
    UNIQUE(business_id, date)
)
```

### 5. Inventory Management
```sql
-- Stock movements tracking
stock_movements (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    movement_type ENUM('in', 'out', 'adjustment') NOT NULL,
    quantity INT NOT NULL,
    reason VARCHAR(255),
    reference_id UUID, -- Could reference order_id or other transactions
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- Low stock alerts
stock_alerts (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    alert_type ENUM('low_stock', 'out_of_stock') NOT NULL,
    threshold_quantity INT,
    is_resolved BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
)
```

## Affiliate Marketing Tables

### 6. Affiliate Management
```sql
-- Affiliate profiles
affiliate_profiles (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    affiliate_code VARCHAR(50) UNIQUE NOT NULL,
    bio TEXT,
    specialization VARCHAR(255),
    social_media_links JSON,
    is_ubuntu_member BOOLEAN DEFAULT false, -- Ubuntu community membership
    tier ENUM('basic', 'silver', 'gold', 'platinum', 'diamond') DEFAULT 'basic',
    total_referrals INT DEFAULT 0,
    total_earnings DECIMAL(10,2) DEFAULT 0,
    conversion_rate DECIMAL(5,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- Commission tiers and rates
commission_tiers (
    id UUID PRIMARY KEY,
    tier_name ENUM('basic', 'silver', 'gold', 'platinum', 'diamond') UNIQUE NOT NULL,
    min_referrals INT NOT NULL,
    max_referrals INT,
    commission_rate DECIMAL(5,2) NOT NULL, -- Percentage
    requirements JSON, -- Additional requirements
    benefits JSON, -- Tier benefits
    is_active BOOLEAN DEFAULT true
)
```

### 7. Campaigns & Referrals
```sql
-- Marketing campaigns
campaigns (
    id UUID PRIMARY KEY,
    business_id UUID REFERENCES msme_businesses(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    campaign_type ENUM('product_launch', 'seasonal', 'discount', 'brand_awareness'),
    commission_rate DECIMAL(5,2) NOT NULL,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    budget DECIMAL(10,2),
    target_audience JSON,
    creative_assets JSON, -- Images, videos, copy
    status ENUM('draft', 'active', 'paused', 'completed') DEFAULT 'draft',
    is_pro_only BOOLEAN DEFAULT false, -- Pro-tier exclusive campaigns
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- Referral links generated by affiliates
referral_links (
    id UUID PRIMARY KEY,
    affiliate_id UUID REFERENCES affiliate_profiles(id),
    campaign_id UUID REFERENCES campaigns(id),
    business_id UUID REFERENCES msme_businesses(id),
    referral_code VARCHAR(100) UNIQUE NOT NULL,
    link_url TEXT NOT NULL,
    platform VARCHAR(50), -- whatsapp, facebook, instagram, etc.
    click_count INT DEFAULT 0,
    conversion_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- Click tracking
link_clicks (
    id UUID PRIMARY KEY,
    referral_link_id UUID REFERENCES referral_links(id),
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,
    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 8. Earnings & Payouts
```sql
-- Affiliate earnings tracking
affiliate_earnings (
    id UUID PRIMARY KEY,
    affiliate_id UUID REFERENCES affiliate_profiles(id),
    referral_link_id UUID REFERENCES referral_links(id),
    order_id UUID REFERENCES orders(id),
    earning_type ENUM('commission', 'bonus', 'tier_bonus', 'ubuntu_bonus') NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ZMW',
    commission_rate DECIMAL(5,2),
    status ENUM('pending', 'confirmed', 'paid') DEFAULT 'pending',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    paid_at TIMESTAMP
)

-- Payout requests and transactions
payouts (
    id UUID PRIMARY KEY,
    affiliate_id UUID REFERENCES affiliate_profiles(id),
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ZMW',
    payment_method ENUM('bank_transfer', 'mobile_money', 'paypal') NOT NULL,
    payment_details JSON, -- Bank account, mobile number, etc.
    status ENUM('requested', 'processing', 'completed', 'failed') DEFAULT 'requested',
    transaction_reference VARCHAR(255),
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    completed_at TIMESTAMP
)

-- Monthly affiliate performance metrics
monthly_affiliate_metrics (
    id UUID PRIMARY KEY,
    affiliate_id UUID REFERENCES affiliate_profiles(id),
    year INT NOT NULL,
    month INT NOT NULL,
    total_clicks INT DEFAULT 0,
    total_conversions INT DEFAULT 0,
    total_earnings DECIMAL(10,2) DEFAULT 0,
    conversion_rate DECIMAL(5,2) DEFAULT 0,
    average_order_value DECIMAL(10,2) DEFAULT 0,
    UNIQUE(affiliate_id, year, month)
)
```

## Ubuntu Community Tables

### 9. Ubuntu Community Features
```sql
-- Ubuntu community members (African unity/cross-promotion)
ubuntu_community_members (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    member_type ENUM('msme', 'affiliate') NOT NULL,
    ubuntu_score INT DEFAULT 0, -- Community participation score
    businesses_helped INT DEFAULT 0,
    mutual_promotions INT DEFAULT 0,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- Cross-promotion activities between Ubuntu members
ubuntu_promotions (
    id UUID PRIMARY KEY,
    promoter_id UUID REFERENCES ubuntu_community_members(id),
    promoted_business_id UUID REFERENCES msme_businesses(id),
    promotion_type ENUM('social_share', 'word_of_mouth', 'cross_referral'),
    description TEXT,
    ubuntu_points_earned INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## System & Analytics Tables

### 10. Notifications & Communications
```sql
-- System notifications
notifications (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    type ENUM('system', 'marketing', 'transaction', 'alert') NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    action_url TEXT,
    priority ENUM('low', 'medium', 'high') DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- Messages between users (customer inquiries, etc.)
messages (
    id UUID PRIMARY KEY,
    sender_id UUID REFERENCES users(id),
    recipient_id UUID REFERENCES users(id),
    subject VARCHAR(255),
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    parent_message_id UUID REFERENCES messages(id), -- For threading
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 11. Analytics & Reporting
```sql
-- System-wide analytics
platform_analytics (
    id UUID PRIMARY KEY,
    date DATE NOT NULL,
    total_active_users INT DEFAULT 0,
    total_msme_businesses INT DEFAULT 0,
    total_affiliates INT DEFAULT 0,
    total_transactions DECIMAL(15,2) DEFAULT 0,
    total_commissions_paid DECIMAL(15,2) DEFAULT 0,
    new_user_registrations INT DEFAULT 0,
    UNIQUE(date)
)

-- User activity logs
user_activity_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    activity_type VARCHAR(100) NOT NULL,
    description TEXT,
    ip_address INET,
    user_agent TEXT,
    metadata JSON, -- Additional context data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 12. Feature Gates & A/B Testing
```sql
-- Feature flags for gradual rollouts
feature_flags (
    id UUID PRIMARY KEY,
    flag_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_enabled BOOLEAN DEFAULT false,
    user_percentage INT DEFAULT 0, -- 0-100% of users
    target_user_types JSON, -- ['msme', 'affiliate', 'pro_users']
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- User-specific feature access
user_feature_access (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    feature_flag_id UUID REFERENCES feature_flags(id),
    has_access BOOLEAN NOT NULL,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, feature_flag_id)
)
```

## Indexes for Performance

```sql
-- Essential indexes for query performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_products_business_id ON products(business_id);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_orders_business_id ON orders(business_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
CREATE INDEX idx_affiliate_earnings_affiliate_id ON affiliate_earnings(affiliate_id);
CREATE INDEX idx_affiliate_earnings_status ON affiliate_earnings(status);
CREATE INDEX idx_referral_links_affiliate_id ON referral_links(affiliate_id);
CREATE INDEX idx_referral_links_campaign_id ON referral_links(campaign_id);
CREATE INDEX idx_link_clicks_referral_link_id ON link_clicks(referral_link_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
```

## Initial Data Requirements

### Default Subscription Plans
- **Basic Plan**: ZMW 0/month (Limited features, basic commission rates)
- **Pro Plan**: ZMW 99/month (Advanced analytics, higher commission rates, pro campaigns)
- **Enterprise Plan**: ZMW 299/month (Full features, priority support, custom commission rates)

### Commission Tiers
- **Basic**: 0-49 referrals, 5% commission
- **Silver**: 50-149 referrals, 7.5% commission  
- **Gold**: 150-299 referrals, 10% commission
- **Platinum**: 300-499 referrals, 12.5% commission
- **Diamond**: 500+ referrals, 15% commission

### Product Categories
- Electronics & Gadgets
- Fashion & Clothing
- Home & Garden
- Health & Beauty
- Food & Beverages
- Handcrafts & Art
- Professional Services
- Education & Training

This database schema supports all the features shown in your frontend application including:
- Dual user roles (MSME + Affiliate)
- Subscription management with feature gates
- Product catalog and inventory management
- Affiliate marketing with referral tracking
- Commission calculations and payouts
- Ubuntu community cross-promotion features
- Analytics and reporting
- Real-time notifications
- Performance tracking and leaderboards
