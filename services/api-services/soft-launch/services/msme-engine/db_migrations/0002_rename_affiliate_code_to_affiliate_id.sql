-- Migration: rename affiliate_code -> affiliate_id on businesses
BEGIN;

-- Rename column if it exists
ALTER TABLE IF EXISTS msme_engine.businesses RENAME COLUMN IF EXISTS affiliate_code TO affiliate_id;

-- Ensure column type matches expectations
ALTER TABLE IF EXISTS msme_engine.businesses ALTER COLUMN IF EXISTS affiliate_id TYPE character varying(36);

-- Recreate index on affiliate_id
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'ix_business_affiliate') THEN
        EXECUTE 'DROP INDEX IF EXISTS msme_engine.ix_business_affiliate';
    END IF;
END$$;
CREATE INDEX IF NOT EXISTS ix_business_affiliate ON msme_engine.businesses (affiliate_id);

-- Migrate event metadata JSON keys from affiliate_code -> affiliate_id
-- This updates any existing records where metadata contains the old key.
UPDATE msme_engine.msme_events
SET metadata = (
    (metadata::jsonb - 'affiliate_code') || jsonb_build_object('affiliate_id', metadata->'affiliate_code')
)::json
WHERE metadata::jsonb ? 'affiliate_code';

COMMIT;
