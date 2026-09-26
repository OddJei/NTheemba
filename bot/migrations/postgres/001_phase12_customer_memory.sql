BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    phone_e164 TEXT NOT NULL UNIQUE,
    phone_hash TEXT GENERATED ALWAYS AS (
        encode(digest(phone_e164, 'sha256'), 'hex')
    ) STORED,
    platform_display_name TEXT,
    preferred_language TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    CONSTRAINT customers_phone_format CHECK (phone_e164 ~ '^\+[0-9]{8,15}$')
);

CREATE INDEX IF NOT EXISTS customers_phone_hash_idx ON customers (phone_hash);
CREATE INDEX IF NOT EXISTS customers_last_seen_idx ON customers (last_seen_at DESC);

CREATE TABLE IF NOT EXISTS customer_consents (
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    consent_type TEXT NOT NULL,
    granted BOOLEAN NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (customer_id, consent_type)
);

CREATE TABLE IF NOT EXISTS business_customers (
    business_customer_id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    preferred_name TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    order_count INTEGER NOT NULL DEFAULT 0 CHECK (order_count >= 0),
    booking_count INTEGER NOT NULL DEFAULT 0 CHECK (booking_count >= 0),
    loyalty_status TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (business_id, customer_id)
);

CREATE INDEX IF NOT EXISTS business_customers_business_last_seen_idx
    ON business_customers (business_id, last_seen_at DESC);

CREATE TABLE IF NOT EXISTS customer_addresses (
    address_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    business_id TEXT,
    label TEXT NOT NULL,
    location_text TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS customer_addresses_default_scope_idx
    ON customer_addresses (customer_id, COALESCE(business_id, '__platform__'))
    WHERE is_default;

CREATE TABLE IF NOT EXISTS customer_preferences (
    preference_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    business_id TEXT,
    preference_key TEXT NOT NULL,
    preference_value JSONB NOT NULL,
    source TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL,
    UNIQUE NULLS NOT DISTINCT (customer_id, business_id, preference_key)
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    business_id TEXT NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    sender_type TEXT NOT NULL CHECK (sender_type IN ('customer', 'assistant', 'human', 'system')),
    message_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS conversation_messages_business_created_idx
    ON conversation_messages (business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS conversation_messages_conversation_created_idx
    ON conversation_messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    summary_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    business_id TEXT NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    intent TEXT NOT NULL,
    outcome TEXT NOT NULL,
    topic TEXT,
    follow_up_required BOOLEAN NOT NULL DEFAULT FALSE,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS conversation_summaries_business_created_idx
    ON conversation_summaries (business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS conversation_summaries_customer_created_idx
    ON conversation_summaries (customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS customer_questions (
    question_id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    question_text TEXT NOT NULL,
    outcome TEXT NOT NULL,
    required_handover BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS customer_questions_business_topic_idx
    ON customer_questions (business_id, topic, created_at DESC);
CREATE INDEX IF NOT EXISTS customer_questions_unresolved_idx
    ON customer_questions (business_id, created_at DESC)
    WHERE outcome IN ('partial', 'unresolved', 'handed_over');

ALTER TABLE business_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_addresses ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_questions ENABLE ROW LEVEL SECURITY;

ALTER TABLE business_customers FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_addresses FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_preferences FORCE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE conversation_summaries FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_questions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS business_customers_tenant_policy ON business_customers;
CREATE POLICY business_customers_tenant_policy ON business_customers
    USING (business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    WITH CHECK (business_id = NULLIF(current_setting('app.business_id', TRUE), ''));

DROP POLICY IF EXISTS customer_addresses_scope_policy ON customer_addresses;
CREATE POLICY customer_addresses_scope_policy ON customer_addresses
    USING (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (
            business_id IS NULL
            OR business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        )
    )
    WITH CHECK (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (
            business_id IS NULL
            OR business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        )
    );

DROP POLICY IF EXISTS customer_preferences_scope_policy ON customer_preferences;
CREATE POLICY customer_preferences_scope_policy ON customer_preferences
    USING (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (
            business_id IS NULL
            OR business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        )
    )
    WITH CHECK (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (
            business_id IS NULL
            OR business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        )
    );


DROP POLICY IF EXISTS conversation_messages_tenant_policy ON conversation_messages;
CREATE POLICY conversation_messages_tenant_policy ON conversation_messages
    USING (business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    WITH CHECK (business_id = NULLIF(current_setting('app.business_id', TRUE), ''));

DROP POLICY IF EXISTS conversation_summaries_tenant_policy ON conversation_summaries;
CREATE POLICY conversation_summaries_tenant_policy ON conversation_summaries
    USING (business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    WITH CHECK (business_id = NULLIF(current_setting('app.business_id', TRUE), ''));

DROP POLICY IF EXISTS customer_questions_tenant_policy ON customer_questions;
CREATE POLICY customer_questions_tenant_policy ON customer_questions
    USING (business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    WITH CHECK (business_id = NULLIF(current_setting('app.business_id', TRUE), ''));

INSERT INTO schema_migrations(version)
VALUES ('001_phase12_customer_memory')
ON CONFLICT (version) DO NOTHING;

COMMIT;
