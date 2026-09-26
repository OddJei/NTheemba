BEGIN;

-- Correct the PostgreSQL regexes installed by 010_runtime_security_hardening.
-- The original patterns over-escaped dots and could allow literal private IPv4
-- integration endpoints such as https://127.0.0.1/ through the durable DB guard.
ALTER TABLE business_integrations
    DROP CONSTRAINT IF EXISTS business_integrations_public_https_endpoint;
ALTER TABLE business_integrations
    ADD CONSTRAINT business_integrations_public_https_endpoint CHECK (
        base_url ~ '^https://'
        AND position('@' in base_url) = 0
        AND position('?' in base_url) = 0
        AND position('#' in base_url) = 0
        AND lower(base_url) !~ '^https://localhost([/:]|$)'
        AND lower(base_url) !~ '^https://127[.]'
        AND lower(base_url) !~ '^https://10[.]'
        AND lower(base_url) !~ '^https://169[.]254[.]'
        AND lower(base_url) !~ '^https://192[.]168[.]'
        AND lower(base_url) !~ '^https://172[.](1[6-9]|2[0-9]|3[0-1])[.]'
    ) NOT VALID;
ALTER TABLE business_integrations
    VALIDATE CONSTRAINT business_integrations_public_https_endpoint;

INSERT INTO schema_migrations (version)
VALUES ('011_runtime_security_private_endpoint_regex')
ON CONFLICT (version) DO NOTHING;

COMMIT;
