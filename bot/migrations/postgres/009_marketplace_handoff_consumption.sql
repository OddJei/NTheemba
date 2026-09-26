BEGIN;

ALTER TABLE marketplace_handoffs
    ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ;

ALTER TABLE marketplace_handoffs
    DROP CONSTRAINT IF EXISTS marketplace_handoffs_consumption_state;
ALTER TABLE marketplace_handoffs
    ADD CONSTRAINT marketplace_handoffs_consumption_state CHECK (
        (status = 'ready' AND consumed_at IS NULL)
        OR (status = 'consumed' AND consumed_at IS NOT NULL)
        OR status = 'cancelled'
    ) NOT VALID;
ALTER TABLE marketplace_handoffs
    VALIDATE CONSTRAINT marketplace_handoffs_consumption_state;

INSERT INTO schema_migrations (version)
VALUES ('009_marketplace_handoff_consumption')
ON CONFLICT (version) DO NOTHING;

COMMIT;
