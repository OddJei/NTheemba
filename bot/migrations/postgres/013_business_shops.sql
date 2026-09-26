BEGIN;

CREATE TABLE IF NOT EXISTS business_shops (
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    shop_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    location JSONB NOT NULL DEFAULT '{}'::jsonb,
    hours_status TEXT NOT NULL DEFAULT 'unverified' CHECK (hours_status IN ('unverified', 'verified')),
    source_revision TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (business_id, shop_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS business_shops_one_primary
    ON business_shops (business_id) WHERE is_primary;

INSERT INTO schema_migrations(version) VALUES ('013_business_shops')
ON CONFLICT (version) DO NOTHING;

COMMIT;
