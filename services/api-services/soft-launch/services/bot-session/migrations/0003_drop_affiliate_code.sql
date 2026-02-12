-- Drop affiliate_code column from session_state_cycles.

DO $$ BEGIN
    ALTER TABLE IF EXISTS session_state_cycles
        DROP COLUMN affiliate_code;
EXCEPTION
    WHEN undefined_column THEN null;
END $$;
