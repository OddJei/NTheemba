BEGIN;

-- PostgreSQL is the durable control-plane authority.  Do not rely solely on
-- API/domain parsing to keep platform capabilities out of a business row:
-- direct persistence must be restricted to this Ntheemba-owned v1 catalogue.
CREATE TABLE IF NOT EXISTS ntheemba_business_capability_catalogue (
    capability_id TEXT PRIMARY KEY,
    CHECK (capability_id IN (
        'business.information',
        'business.hours',
        'faq.search',
        'client.identify',
        'client.create',
        'product.catalogue',
        'product.order',
        'fulfilment.delivery',
        'fulfilment.collection',
        'service.catalogue',
        'appointment.create',
        'appointment.reschedule',
        'appointment.cancel',
        'loyalty.read',
        'handover.create'
    ))
);

INSERT INTO ntheemba_business_capability_catalogue (capability_id)
VALUES
    ('business.information'),
    ('business.hours'),
    ('faq.search'),
    ('client.identify'),
    ('client.create'),
    ('product.catalogue'),
    ('product.order'),
    ('fulfilment.delivery'),
    ('fulfilment.collection'),
    ('service.catalogue'),
    ('appointment.create'),
    ('appointment.reschedule'),
    ('appointment.cancel'),
    ('loyalty.read'),
    ('handover.create')
ON CONFLICT (capability_id) DO NOTHING;

-- Preserve the explicit Marketplace defence as a readable invariant, while
-- the foreign key below rejects every non-canonical spelling/alias.
ALTER TABLE business_capabilities
    DROP CONSTRAINT IF EXISTS business_capabilities_no_platform_capability;
ALTER TABLE business_capabilities
    ADD CONSTRAINT business_capabilities_no_platform_capability
        CHECK (
            lower(regexp_replace(capability_id, '[^[:alnum:]]+', '', 'g'))
                NOT IN ('marketplace', 'platformmarketplace')
        ) NOT VALID;
ALTER TABLE business_capabilities
    VALIDATE CONSTRAINT business_capabilities_no_platform_capability;

ALTER TABLE business_capabilities
    DROP CONSTRAINT IF EXISTS business_capabilities_canonical_capability_fk;
ALTER TABLE business_capabilities
    ADD CONSTRAINT business_capabilities_canonical_capability_fk
        FOREIGN KEY (capability_id)
        REFERENCES ntheemba_business_capability_catalogue(capability_id)
        NOT VALID;
ALTER TABLE business_capabilities
    VALIDATE CONSTRAINT business_capabilities_canonical_capability_fk;

INSERT INTO schema_migrations (version)
VALUES ('012_business_capability_catalogue')
ON CONFLICT (version) DO NOTHING;

COMMIT;
