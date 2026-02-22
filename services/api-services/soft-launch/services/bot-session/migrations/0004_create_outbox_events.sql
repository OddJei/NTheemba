-- Create service-schema outbox_events table (compatible with other services)
DO $$ BEGIN
    CREATE SCHEMA IF NOT EXISTS bot_session;
EXCEPTION
    WHEN duplicate_schema THEN null;
END $$;

CREATE TABLE IF NOT EXISTS bot_session.outbox_events (
  id VARCHAR(36) PRIMARY KEY,
  event_type VARCHAR(100),
  topic VARCHAR(100),
  destination VARCHAR(200),
  payload JSONB,
  headers JSONB,
  producer VARCHAR(100),
  correlation_id VARCHAR(255),
  dedupe_key VARCHAR(255),
  status VARCHAR(30) DEFAULT 'pending',
  attempts INTEGER DEFAULT 0,
  last_error VARCHAR(2000),
  last_response JSONB,
  scheduled_at TIMESTAMPTZ,
  priority INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bot_session_outbox_event_type ON bot_session.outbox_events (event_type);
CREATE INDEX IF NOT EXISTS ix_bot_session_outbox_topic ON bot_session.outbox_events (topic);
CREATE INDEX IF NOT EXISTS ix_bot_session_outbox_correlation_id ON bot_session.outbox_events (correlation_id);
