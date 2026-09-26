BEGIN;

CREATE TABLE IF NOT EXISTS marketplace_business_listings (
    business_id TEXT PRIMARY KEY REFERENCES businesses(business_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'paused', 'rejected')),
    discoverable BOOLEAN NOT NULL DEFAULT FALSE,
    province_id TEXT NOT NULL DEFAULT '',
    district_id TEXT NOT NULL DEFAULT '',
    town_id TEXT NOT NULL DEFAULT '',
    area_text TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (discoverable = FALSE OR status = 'active')
);

-- Defence in depth: Marketplace remains platform policy and never becomes a business capability.
ALTER TABLE business_capabilities
    DROP CONSTRAINT IF EXISTS business_capabilities_no_platform_capability;
ALTER TABLE business_capabilities
    ADD CONSTRAINT business_capabilities_no_platform_capability
        CHECK (capability_id NOT IN ('marketplace', 'platform.marketplace')) NOT VALID;
ALTER TABLE business_capabilities
    VALIDATE CONSTRAINT business_capabilities_no_platform_capability;

INSERT INTO schema_migrations (version)
VALUES ('007_marketplace_participation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
