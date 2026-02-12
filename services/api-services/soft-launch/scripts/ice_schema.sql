CREATE SCHEMA IF NOT EXISTS ice_service;
SET search_path TO ice_service;

CREATE TABLE IF NOT EXISTS ice_sessions (
  id VARCHAR PRIMARY KEY,
  session_id VARCHAR NOT NULL UNIQUE,
  phone_number VARCHAR NOT NULL,
  business_id VARCHAR NOT NULL,
  blob JSON NOT NULL,
  schema_version VARCHAR,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_ice_sessions_business_id ON ice_sessions (business_id);
CREATE INDEX IF NOT EXISTS ix_ice_sessions_phone_number ON ice_sessions (phone_number);
CREATE INDEX IF NOT EXISTS ix_ice_sessions_session_id ON ice_sessions (session_id);

CREATE TABLE IF NOT EXISTS ice_order_drafts (
  id VARCHAR PRIMARY KEY,
  session_id VARCHAR NOT NULL,
  order_id VARCHAR,
  blob JSON NOT NULL,
  status VARCHAR,
  schema_version VARCHAR,
  idempotency_key VARCHAR UNIQUE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_ice_order_drafts_session_id ON ice_order_drafts (session_id);
CREATE INDEX IF NOT EXISTS ix_ice_order_drafts_order_id ON ice_order_drafts (order_id);

CREATE TABLE IF NOT EXISTS ice_product_snapshots (
  id VARCHAR PRIMARY KEY,
  business_id VARCHAR NOT NULL,
  product_id VARCHAR NOT NULL,
  variant_id VARCHAR,
  blob JSON NOT NULL,
  schema_version VARCHAR,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_product_snapshots_business_product ON ice_product_snapshots (business_id, product_id);
CREATE INDEX IF NOT EXISTS ix_ice_product_snapshots_business_id ON ice_product_snapshots (business_id);
CREATE INDEX IF NOT EXISTS ix_ice_product_snapshots_product_id ON ice_product_snapshots (product_id);
CREATE INDEX IF NOT EXISTS ix_ice_product_snapshots_variant_id ON ice_product_snapshots (variant_id);

CREATE TABLE IF NOT EXISTS ice_catalog_snapshots (
  id VARCHAR PRIMARY KEY,
  business_id VARCHAR NOT NULL UNIQUE,
  blob JSON NOT NULL,
  schema_version VARCHAR,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_ice_catalog_snapshots_business_id ON ice_catalog_snapshots (business_id);

CREATE TABLE IF NOT EXISTS ice_affiliate_contexts (
  id VARCHAR PRIMARY KEY,
  session_id VARCHAR NOT NULL,
  order_id VARCHAR,
  affiliate_id VARCHAR,
  blob JSON NOT NULL,
  status VARCHAR,
  schema_version VARCHAR,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_ice_affiliate_contexts_session_id ON ice_affiliate_contexts (session_id);
CREATE INDEX IF NOT EXISTS ix_ice_affiliate_contexts_order_id ON ice_affiliate_contexts (order_id);
CREATE INDEX IF NOT EXISTS ix_ice_affiliate_contexts_affiliate_id ON ice_affiliate_contexts (affiliate_id);

CREATE TABLE IF NOT EXISTS ice_audit_logs (
  id VARCHAR PRIMARY KEY,
  session_id VARCHAR NOT NULL,
  order_id VARCHAR,
  business_id VARCHAR,
  event_type VARCHAR NOT NULL,
  event_payload JSON,
  correlation_id VARCHAR,
  idempotency_key VARCHAR,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_session_id ON ice_audit_logs (session_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_event_type ON ice_audit_logs (event_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON ice_audit_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_ice_audit_logs_order_id ON ice_audit_logs (order_id);
CREATE INDEX IF NOT EXISTS ix_ice_audit_logs_business_id ON ice_audit_logs (business_id);

CREATE TABLE IF NOT EXISTS ice_idempotency_cache (
  id VARCHAR PRIMARY KEY,
  idempotency_key VARCHAR NOT NULL UNIQUE,
  request_method VARCHAR NOT NULL,
  request_path VARCHAR NOT NULL,
  response_status VARCHAR NOT NULL,
  response_body JSON NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ice_idempotency_cache_key ON ice_idempotency_cache (idempotency_key);

CREATE TABLE IF NOT EXISTS ice_message_log (
  id VARCHAR PRIMARY KEY,
  correlation_id VARCHAR UNIQUE,
  session_id VARCHAR NOT NULL,
  business_id VARCHAR,
  user_phone VARCHAR,
  bot_phone VARCHAR,
  incoming_message TEXT,
  incoming_payload JSON,
  incoming_at TIMESTAMPTZ,
  outgoing_message TEXT,
  outgoing_payload JSON,
  outgoing_status VARCHAR, -- pending | sent | failed
  outgoing_at TIMESTAMPTZ,
  provider_message_id VARCHAR,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_ice_message_log_correlation_id ON ice_message_log (correlation_id);
CREATE INDEX IF NOT EXISTS ix_ice_message_log_session_id ON ice_message_log (session_id);
CREATE INDEX IF NOT EXISTS ix_ice_message_log_business_id ON ice_message_log (business_id);
CREATE INDEX IF NOT EXISTS ix_ice_message_log_status ON ice_message_log (outgoing_status);

ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS correlation_id VARCHAR;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS incoming_message TEXT;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS incoming_payload JSON;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS incoming_at TIMESTAMPTZ;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS outgoing_message TEXT;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS outgoing_payload JSON;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS outgoing_status VARCHAR;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS outgoing_at TIMESTAMPTZ;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS provider_message_id VARCHAR;
ALTER TABLE ice_message_log ADD COLUMN IF NOT EXISTS error_message TEXT;
