CREATE TABLE IF NOT EXISTS msme_engine.subscription_pricing (
  billing_interval varchar(10) PRIMARY KEY,
  amount_minor integer NOT NULL,
  currency varchar(10) NOT NULL DEFAULT 'ZMW',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
