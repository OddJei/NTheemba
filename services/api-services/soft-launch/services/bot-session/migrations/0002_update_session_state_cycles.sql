-- Update session_state_cycles schema: rename column and adjust defaults/constraints.

DO $$ BEGIN
    ALTER TABLE IF EXISTS session_state_cycles RENAME COLUMN cycle_type TO cycle_state;
EXCEPTION
    WHEN undefined_column THEN null;
END $$;

ALTER TABLE IF EXISTS session_state_cycles
    ALTER COLUMN cycle_state SET DEFAULT 'chat',
    ALTER COLUMN initiated_by_affiliate SET DEFAULT true;

UPDATE session_state_cycles
SET cycle_state = 'chat'
WHERE cycle_state IS NULL;

UPDATE session_state_cycles
SET initiated_by_affiliate = CASE WHEN affiliate_id IS NULL THEN false ELSE true END
WHERE initiated_by_affiliate IS NULL
   OR (affiliate_id IS NULL AND initiated_by_affiliate IS TRUE)
   OR (affiliate_id IS NOT NULL AND initiated_by_affiliate IS FALSE);

DO $$ BEGIN
    ALTER TABLE IF EXISTS session_state_cycles
        ADD CONSTRAINT chk_session_state_cycles_affiliate_id
        CHECK (
            (initiated_by_affiliate = true AND affiliate_id IS NOT NULL)
            OR (initiated_by_affiliate = false AND affiliate_id IS NULL)
        );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
