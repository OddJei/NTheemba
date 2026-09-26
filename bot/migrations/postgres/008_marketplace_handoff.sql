BEGIN;

CREATE TABLE IF NOT EXISTS marketplace_handoffs (
    handoff_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL,
    result_id TEXT NOT NULL,
    source_channel_id TEXT NOT NULL REFERENCES business_channels(channel_instance_id),
    target_business_id TEXT NOT NULL REFERENCES businesses(business_id),
    business_product_id TEXT NOT NULL,
    ncpc_product_id TEXT NOT NULL,
    ncpc_variant_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    selling_price_snapshot NUMERIC(18, 4) NOT NULL CHECK (selling_price_snapshot >= 0),
    currency TEXT NOT NULL CHECK (char_length(currency) = 3),
    integration_id TEXT NOT NULL,
    business_runtime_revision BIGINT NOT NULL CHECK (business_runtime_revision >= 0),
    shop_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ready'
        CHECK (status IN ('ready', 'consumed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (search_id, result_id)
);

CREATE INDEX IF NOT EXISTS marketplace_handoffs_target_business_idx
    ON marketplace_handoffs (target_business_id, created_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('008_marketplace_handoff')
ON CONFLICT (version) DO NOTHING;

COMMIT;
