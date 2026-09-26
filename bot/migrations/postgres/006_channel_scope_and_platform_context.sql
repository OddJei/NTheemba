BEGIN;

ALTER TABLE business_channels
    ADD COLUMN IF NOT EXISTS scope TEXT NOT NULL DEFAULT 'business',
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'business_primary',
    ADD COLUMN IF NOT EXISTS is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS external_session_id TEXT,
    ADD COLUMN IF NOT EXISTS recipient_identifier TEXT;

UPDATE business_channels
   SET external_session_id = COALESCE(NULLIF(external_session_id, ''), channel_instance_id),
       recipient_identifier = COALESCE(NULLIF(recipient_identifier, ''), phone_e164)
 WHERE external_session_id IS NULL
    OR external_session_id = ''
    OR recipient_identifier IS NULL
    OR recipient_identifier = '';

ALTER TABLE business_channels
    ALTER COLUMN external_session_id SET NOT NULL,
    ALTER COLUMN recipient_identifier SET NOT NULL,
    ALTER COLUMN business_id DROP NOT NULL;

ALTER TABLE business_channels
    DROP CONSTRAINT IF EXISTS business_channels_scope_check,
    DROP CONSTRAINT IF EXISTS business_channels_role_check,
    DROP CONSTRAINT IF EXISTS business_channels_scope_owner_check;

ALTER TABLE business_capabilities
    DROP CONSTRAINT IF EXISTS business_capabilities_no_platform_capability;
ALTER TABLE business_capabilities
    ADD CONSTRAINT business_capabilities_no_platform_capability
        CHECK (capability_id <> 'marketplace') NOT VALID;
ALTER TABLE business_capabilities
    VALIDATE CONSTRAINT business_capabilities_no_platform_capability;

ALTER TABLE business_channels
    ADD CONSTRAINT business_channels_scope_check
        CHECK (scope IN ('business', 'platform')),
    ADD CONSTRAINT business_channels_role_check
        CHECK (role IN (
            'business_primary', 'business_secondary',
            'marketplace', 'platform_general', 'platform_support'
        )),
    ADD CONSTRAINT business_channels_scope_owner_check
        CHECK (
            (scope = 'business' AND business_id IS NOT NULL
             AND role IN ('business_primary', 'business_secondary'))
            OR
            (scope = 'platform' AND business_id IS NULL
             AND role IN ('marketplace', 'platform_general', 'platform_support'))
        );

CREATE UNIQUE INDEX IF NOT EXISTS business_channels_exact_identity_uidx
    ON business_channels (provider, external_session_id, recipient_identifier);

CREATE UNIQUE INDEX IF NOT EXISTS business_channels_primary_business_role_uidx
    ON business_channels (business_id, role)
    WHERE scope = 'business' AND is_primary = TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS business_channels_primary_platform_role_uidx
    ON business_channels (role)
    WHERE scope = 'platform' AND is_primary = TRUE;

INSERT INTO schema_migrations (version)
VALUES ('006_channel_scope_and_platform_context')
ON CONFLICT (version) DO NOTHING;

COMMIT;
