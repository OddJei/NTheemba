BEGIN;

ALTER TABLE businesses
    ADD COLUMN IF NOT EXISTS runtime_revision BIGINT NOT NULL DEFAULT 1;

ALTER TABLE business_capabilities
    ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS business_integrations (
    integration_id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'google_apps_script',
    adapter_type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_version TEXT NOT NULL DEFAULT 'tradeflow.ntheemba.v1',
    auth_reference TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    capabilities TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT business_integrations_capabilities_not_empty
        CHECK (array_length(capabilities, 1) IS NOT NULL),
    CONSTRAINT business_integrations_base_url_not_empty
        CHECK (length(btrim(base_url)) > 0),
    CONSTRAINT business_integrations_status_known
        CHECK (status IN ('active', 'inactive', 'testing', 'disabled'))
);

ALTER TABLE business_integrations
    ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'google_apps_script',
    ADD COLUMN IF NOT EXISTS api_version TEXT NOT NULL DEFAULT 'tradeflow.ntheemba.v1',
    ADD COLUMN IF NOT EXISTS auth_reference TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';

CREATE INDEX IF NOT EXISTS business_integrations_business_idx
    ON business_integrations (business_id, enabled);

CREATE INDEX IF NOT EXISTS businesses_runtime_revision_idx
    ON businesses (business_id, runtime_revision);

INSERT INTO business_integrations (
    integration_id, business_id, provider, adapter_type, base_url,
    api_version, auth_reference, status, enabled, capabilities, config
) VALUES
    (
        'harvest-tradeflow-standard',
        'harvest-big-shop',
        'google_apps_script',
        'tradeflow_standard',
        'https://tradeflow.local/harvest',
        'tradeflow.ntheemba.v1',
        'script_properties:NTHEEMBA_API_TOKEN',
        'testing',
        TRUE,
        ARRAY[
            'business.information', 'business.hours', 'faq.search',
            'product.catalogue', 'product.order',
            'fulfilment.delivery', 'fulfilment.collection', 'handover.create'
        ],
        '{"contract":"tradeflow.ntheemba.v1"}'::jsonb
    ),
    (
        'amac-tradeflow-standard',
        'amac-enterprise',
        'google_apps_script',
        'tradeflow_standard',
        'https://tradeflow.local/amac',
        'tradeflow.ntheemba.v1',
        'script_properties:NTHEEMBA_API_TOKEN',
        'testing',
        TRUE,
        ARRAY[
            'business.information', 'business.hours', 'faq.search',
            'product.catalogue', 'product.order',
            'fulfilment.collection', 'handover.create'
        ],
        '{"contract":"tradeflow.ntheemba.v1"}'::jsonb
    ),
    (
        'serahs-tradeflow-custom',
        'serahs-glow-lounge',
        'google_apps_script',
        'tradeflow_serahs',
        'https://tradeflow.local/serahs-glow',
        'tradeflow.ntheemba.v1',
        'script_properties:NTHEEMBA_API_TOKEN',
        'testing',
        TRUE,
        ARRAY[
            'business.information', 'business.hours', 'faq.search',
            'client.identify', 'client.create',
            'product.catalogue', 'product.order', 'fulfilment.collection',
            'service.catalogue', 'appointment.create',
            'appointment.reschedule', 'appointment.cancel',
            'loyalty.read', 'handover.create'
        ],
        '{"contract":"tradeflow.ntheemba.v1"}'::jsonb
    )
ON CONFLICT (integration_id) DO UPDATE SET
    provider = EXCLUDED.provider,
    adapter_type = EXCLUDED.adapter_type,
    base_url = EXCLUDED.base_url,
    api_version = EXCLUDED.api_version,
    auth_reference = EXCLUDED.auth_reference,
    status = EXCLUDED.status,
    enabled = EXCLUDED.enabled,
    capabilities = EXCLUDED.capabilities,
    config = EXCLUDED.config,
    updated_at = NOW();

UPDATE businesses
   SET runtime_revision = runtime_revision + 1,
       updated_at = NOW()
 WHERE business_id IN ('harvest-big-shop', 'amac-enterprise', 'serahs-glow-lounge');

INSERT INTO schema_migrations(version) VALUES ('004_runtime_profiles_and_integrations')
ON CONFLICT (version) DO NOTHING;

COMMIT;
