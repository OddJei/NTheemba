BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS businesses (
    business_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    business_type TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS business_capabilities (
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    capability_id TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    declared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (business_id, capability_id)
);

CREATE TABLE IF NOT EXISTS business_channels (
    channel_instance_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    phone_e164 TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, phone_e164),
    CONSTRAINT business_channels_phone_format CHECK (phone_e164 ~ '^\+[0-9]{8,15}$')
);

CREATE INDEX IF NOT EXISTS business_channels_business_idx ON business_channels (business_id);

CREATE TABLE IF NOT EXISTS unsupported_declarations (
    observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL CHECK (kind IN ('capability', 'tradeflow_operation')),
    value TEXT NOT NULL,
    business_id TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    source TEXT NOT NULL,
    first_observed_at TIMESTAMPTZ NOT NULL,
    last_observed_at TIMESTAMPTZ NOT NULL,
    observation_count BIGINT NOT NULL DEFAULT 1 CHECK (observation_count > 0),
    UNIQUE (kind, value, business_id, adapter_type, source)
);

CREATE INDEX IF NOT EXISTS unsupported_declarations_last_seen_idx
    ON unsupported_declarations (last_observed_at DESC);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    phone_e164 TEXT NOT NULL UNIQUE,
    phone_hash TEXT GENERATED ALWAYS AS (encode(digest(phone_e164, 'sha256'), 'hex')) STORED,
    preferred_name TEXT NOT NULL DEFAULT '',
    preferred_language TEXT NOT NULL DEFAULT 'en',
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

CREATE TABLE IF NOT EXISTS business_clients (
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    external_client_id TEXT NOT NULL,
    business_display_name TEXT NOT NULL DEFAULT '',
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (business_id, customer_id),
    UNIQUE (business_id, external_client_id)
);

CREATE INDEX IF NOT EXISTS business_clients_last_seen_idx
    ON business_clients (business_id, last_seen_at DESC);

CREATE TABLE IF NOT EXISTS customer_addresses (
    address_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    business_id TEXT REFERENCES businesses(business_id) ON DELETE CASCADE,
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
    business_id TEXT REFERENCES businesses(business_id) ON DELETE CASCADE,
    preference_key TEXT NOT NULL,
    preference_value JSONB NOT NULL,
    source TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL,
    UNIQUE NULLS NOT DISTINCT (customer_id, business_id, preference_key)
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    sender_type TEXT NOT NULL CHECK (sender_type IN ('customer', 'assistant', 'human', 'system')),
    message_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS conversation_messages_conversation_idx
    ON conversation_messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS conversation_messages_business_idx
    ON conversation_messages (business_id, created_at DESC);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    summary_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    intent TEXT NOT NULL,
    outcome TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    follow_up_required BOOLEAN NOT NULL DEFAULT FALSE,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS conversation_summaries_customer_idx
    ON conversation_summaries (business_id, customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS customer_questions (
    question_id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
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

ALTER TABLE business_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_addresses ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_questions ENABLE ROW LEVEL SECURITY;

ALTER TABLE business_clients FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_addresses FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_preferences FORCE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE conversation_summaries FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_questions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS business_clients_tenant_policy ON business_clients;
CREATE POLICY business_clients_tenant_policy ON business_clients
    USING (business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    WITH CHECK (business_id = NULLIF(current_setting('app.business_id', TRUE), ''));

DROP POLICY IF EXISTS customer_addresses_scope_policy ON customer_addresses;
CREATE POLICY customer_addresses_scope_policy ON customer_addresses
    USING (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (business_id IS NULL OR business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    )
    WITH CHECK (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (business_id IS NULL OR business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    );

DROP POLICY IF EXISTS customer_preferences_scope_policy ON customer_preferences;
CREATE POLICY customer_preferences_scope_policy ON customer_preferences
    USING (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (business_id IS NULL OR business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    )
    WITH CHECK (
        customer_id = NULLIF(current_setting('app.customer_id', TRUE), '')
        AND (business_id IS NULL OR business_id = NULLIF(current_setting('app.business_id', TRUE), ''))
    );

DROP POLICY IF EXISTS conversation_messages_tenant_policy ON conversation_messages;
CREATE POLICY conversation_messages_tenant_policy ON conversation_messages
    USING (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    )
    WITH CHECK (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    );

DROP POLICY IF EXISTS conversation_summaries_tenant_policy ON conversation_summaries;
CREATE POLICY conversation_summaries_tenant_policy ON conversation_summaries
    USING (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    )
    WITH CHECK (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    );

DROP POLICY IF EXISTS customer_questions_tenant_policy ON customer_questions;
CREATE POLICY customer_questions_tenant_policy ON customer_questions
    USING (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    )
    WITH CHECK (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    );

INSERT INTO schema_migrations(version) VALUES ('001_phase12_core')
ON CONFLICT (version) DO NOTHING;

COMMIT;
