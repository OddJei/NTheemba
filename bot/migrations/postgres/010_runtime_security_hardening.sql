BEGIN;

-- External channel identities are canonicalized before persistence so provider-case
-- variants cannot bypass the exact channel uniqueness boundary.
UPDATE business_channels
   SET provider = lower(btrim(provider)),
       external_session_id = btrim(external_session_id),
       recipient_identifier = btrim(recipient_identifier);

ALTER TABLE business_channels
    DROP CONSTRAINT IF EXISTS business_channels_canonical_identity;
ALTER TABLE business_channels
    ADD CONSTRAINT business_channels_canonical_identity CHECK (
        provider = lower(btrim(provider))
        AND external_session_id = btrim(external_session_id)
        AND length(external_session_id) > 0
        AND recipient_identifier = btrim(recipient_identifier)
        AND length(recipient_identifier) > 0
    ) NOT VALID;
ALTER TABLE business_channels
    VALIDATE CONSTRAINT business_channels_canonical_identity;

-- Secret values never belong in durable integration configuration.  The runtime
-- accepts opaque references (env:NAME, script_properties:NAME, future resolvers)
-- and resolves them only inside the adapter factory.
ALTER TABLE business_integrations
    DROP CONSTRAINT IF EXISTS business_integrations_auth_reference_is_reference,
    DROP CONSTRAINT IF EXISTS business_integrations_no_top_level_secret_values,
    DROP CONSTRAINT IF EXISTS business_integrations_public_https_endpoint;
ALTER TABLE business_integrations
    ADD CONSTRAINT business_integrations_auth_reference_is_reference CHECK (
        auth_reference = ''
        OR auth_reference ~ '^[a-z][a-z0-9_]*:[A-Za-z0-9_.-]+$'
    ) NOT VALID,
    ADD CONSTRAINT business_integrations_no_top_level_secret_values CHECK (
        NOT (config ?| ARRAY[
            'api_token', 'token', 'password', 'secret', 'signing_secret',
            'credential', 'credentials', 'api_key', 'apikey'
        ])
    ) NOT VALID,
    ADD CONSTRAINT business_integrations_public_https_endpoint CHECK (
        base_url ~ '^https://'
        AND position('@' in base_url) = 0
        AND position('?' in base_url) = 0
        AND position('#' in base_url) = 0
        AND lower(base_url) !~ '^https://localhost([/:]|$)'
        AND lower(base_url) !~ '^https://127\\.'
        AND lower(base_url) !~ '^https://10\\.'
        AND lower(base_url) !~ '^https://169\\.254\\.'
        AND lower(base_url) !~ '^https://192\\.168\\.'
        AND lower(base_url) !~ '^https://172\\.(1[6-9]|2[0-9]|3[0-1])\\.'
    ) NOT VALID;
ALTER TABLE business_integrations
    VALIDATE CONSTRAINT business_integrations_auth_reference_is_reference;
ALTER TABLE business_integrations
    VALIDATE CONSTRAINT business_integrations_no_top_level_secret_values;
ALTER TABLE business_integrations
    VALIDATE CONSTRAINT business_integrations_public_https_endpoint;

-- Marketplace handoffs must point at an integration owned by the selected tenant.
ALTER TABLE business_integrations
    DROP CONSTRAINT IF EXISTS business_integrations_id_business_unique;
ALTER TABLE business_integrations
    ADD CONSTRAINT business_integrations_id_business_unique
        UNIQUE (integration_id, business_id);

ALTER TABLE marketplace_handoffs
    DROP CONSTRAINT IF EXISTS marketplace_handoffs_integration_tenant_fk;
ALTER TABLE marketplace_handoffs
    ADD CONSTRAINT marketplace_handoffs_integration_tenant_fk
        FOREIGN KEY (integration_id, target_business_id)
        REFERENCES business_integrations(integration_id, business_id)
        NOT VALID;
ALTER TABLE marketplace_handoffs
    VALIDATE CONSTRAINT marketplace_handoffs_integration_tenant_fk;

-- A Marketplace handoff can originate only from an enabled PLATFORM/MARKETPLACE
-- channel. PostgreSQL CHECK constraints cannot query the channel table, so use a
-- narrow trigger as defence in depth against direct persistence bypasses.
CREATE OR REPLACE FUNCTION enforce_marketplace_handoff_source_channel()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    channel_scope TEXT;
    channel_role TEXT;
    channel_enabled BOOLEAN;
BEGIN
    SELECT scope, role, enabled
      INTO channel_scope, channel_role, channel_enabled
      FROM business_channels
     WHERE channel_instance_id = NEW.source_channel_id;

    IF channel_scope IS DISTINCT FROM 'platform'
       OR channel_role IS DISTINCT FROM 'marketplace'
       OR channel_enabled IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'marketplace handoff source must be an enabled platform marketplace channel';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS marketplace_handoffs_source_channel_guard ON marketplace_handoffs;
CREATE TRIGGER marketplace_handoffs_source_channel_guard
BEFORE INSERT OR UPDATE OF source_channel_id ON marketplace_handoffs
FOR EACH ROW EXECUTE FUNCTION enforce_marketplace_handoff_source_channel();

INSERT INTO schema_migrations (version)
VALUES ('010_runtime_security_hardening')
ON CONFLICT (version) DO NOTHING;

COMMIT;
