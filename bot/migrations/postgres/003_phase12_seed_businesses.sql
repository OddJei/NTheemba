BEGIN;

-- Development seeds are intentionally idempotent and use placeholder channel numbers.
INSERT INTO businesses (business_id, display_name, adapter_type, business_type, description)
VALUES
    ('harvest-big-shop', 'Harvest Big Shop', 'tradeflow_standard', 'retail', 'Standard TradeFlow reference business'),
    ('amac-enterprise', 'AMAC Enterprise', 'tradeflow_standard', 'retail', 'Standard TradeFlow reference business'),
    ('serahs-glow-lounge', 'Serah''s Glow Lounge', 'tradeflow_serahs', 'beauty-salon-retail', 'Custom TradeFlow service reference business')
ON CONFLICT (business_id) DO NOTHING;

INSERT INTO business_capabilities (business_id, capability_id)
VALUES
    ('harvest-big-shop', 'business.information'), ('harvest-big-shop', 'business.hours'), ('harvest-big-shop', 'faq.search'),
    ('harvest-big-shop', 'product.catalogue'), ('harvest-big-shop', 'product.order'), ('harvest-big-shop', 'fulfilment.delivery'),
    ('harvest-big-shop', 'fulfilment.collection'), ('harvest-big-shop', 'handover.create'),
    ('amac-enterprise', 'business.information'), ('amac-enterprise', 'business.hours'), ('amac-enterprise', 'faq.search'),
    ('amac-enterprise', 'product.catalogue'), ('amac-enterprise', 'product.order'), ('amac-enterprise', 'fulfilment.collection'),
    ('amac-enterprise', 'handover.create'),
    ('serahs-glow-lounge', 'business.information'), ('serahs-glow-lounge', 'business.hours'),
    ('serahs-glow-lounge', 'faq.search'), ('serahs-glow-lounge', 'client.identify'), ('serahs-glow-lounge', 'client.create'),
    ('serahs-glow-lounge', 'product.catalogue'), ('serahs-glow-lounge', 'product.order'),
    ('serahs-glow-lounge', 'fulfilment.collection'), ('serahs-glow-lounge', 'service.catalogue'),
    ('serahs-glow-lounge', 'appointment.create'), ('serahs-glow-lounge', 'appointment.reschedule'),
    ('serahs-glow-lounge', 'appointment.cancel'), ('serahs-glow-lounge', 'loyalty.read'),
    ('serahs-glow-lounge', 'handover.create')
ON CONFLICT DO NOTHING;

-- Local simulator channels. Replace or register real OpenWA channels before production use.
INSERT INTO business_channels (
    channel_instance_id, provider, business_id, phone_e164, enabled
) VALUES
    ('sim-wa-harvest', 'openwa-simulator', 'harvest-big-shop', '+260970000001', TRUE),
    ('sim-wa-amac', 'openwa-simulator', 'amac-enterprise', '+260970000002', TRUE),
    ('sim-wa-serahs', 'openwa-simulator', 'serahs-glow-lounge', '+260976078440', TRUE)
ON CONFLICT (channel_instance_id) DO UPDATE SET
    provider = EXCLUDED.provider,
    business_id = EXCLUDED.business_id,
    phone_e164 = EXCLUDED.phone_e164,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

INSERT INTO schema_migrations(version) VALUES ('003_phase12_seed_businesses')
ON CONFLICT (version) DO NOTHING;

COMMIT;
