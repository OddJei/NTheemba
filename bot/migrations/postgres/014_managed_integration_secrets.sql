BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS managed_integration_secrets (
    secret_reference TEXT PRIMARY KEY CHECK (secret_reference ~ '^managed:[A-Za-z0-9_.-]+$'),
    ciphertext BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations(version) VALUES ('014_managed_integration_secrets')
ON CONFLICT (version) DO NOTHING;

COMMIT;
