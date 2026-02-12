-- Add delivery_locations column (Postgres)
ALTER TABLE IF EXISTS msme_engine.businesses
    ADD COLUMN IF NOT EXISTS delivery_locations JSONB;

-- Optional: populate from existing default if needed
-- UPDATE msme_engine.businesses SET delivery_locations = '{}' WHERE delivery_locations IS NULL;
