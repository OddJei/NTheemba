BEGIN;

CREATE TABLE IF NOT EXISTS operational_audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    request_id TEXT NOT NULL,
    business_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    conversation_id TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    occurred_at TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS operational_audit_events_business_time_idx
    ON operational_audit_events (business_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS operational_audit_events_request_idx
    ON operational_audit_events (request_id);
CREATE INDEX IF NOT EXISTS operational_audit_events_type_time_idx
    ON operational_audit_events (event_type, occurred_at DESC);

ALTER TABLE operational_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE operational_audit_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS operational_audit_events_tenant_policy ON operational_audit_events;
CREATE POLICY operational_audit_events_tenant_policy ON operational_audit_events
    USING (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    )
    WITH CHECK (
        business_id = NULLIF(current_setting('app.business_id', TRUE), '')
        OR current_setting('app.system_maintenance', TRUE) = 'on'
    );

INSERT INTO schema_migrations(version) VALUES ('005_operational_audit')
ON CONFLICT (version) DO NOTHING;

COMMIT;
