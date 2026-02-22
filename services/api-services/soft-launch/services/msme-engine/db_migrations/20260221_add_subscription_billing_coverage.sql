ALTER TABLE IF EXISTS business_subscriptions
ADD COLUMN IF NOT EXISTS billing_interval varchar(10) NOT NULL DEFAULT 'monthly';

ALTER TABLE IF EXISTS business_subscriptions
ADD COLUMN IF NOT EXISTS periods_paid numeric(8,4) NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS business_subscriptions
ADD COLUMN IF NOT EXISTS paid_through timestamptz NULL;
