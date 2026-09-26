"""Static checks for Phase 12 migration safety and capability ownership."""

import re
from pathlib import Path

from ntheemba.domain.capabilities import Capability

MIGRATIONS = Path("migrations/postgres")


def test_business_seed_declares_only_ntheemba_known_capabilities() -> None:
    sql = (MIGRATIONS / "003_phase12_seed_businesses.sql").read_text()
    declared = set(re.findall(r"'([a-z]+\.[a-z_]+)'", sql))
    known = {capability.value for capability in Capability}

    assert declared
    assert declared <= known


def test_core_migration_forces_tenant_row_level_security() -> None:
    sql = (MIGRATIONS / "001_phase12_core.sql").read_text()

    for table in (
        "business_clients",
        "customer_addresses",
        "customer_preferences",
        "conversation_messages",
        "conversation_summaries",
        "customer_questions",
    ):
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql


def test_retention_cleanup_explicitly_enters_maintenance_scope() -> None:
    sql = (MIGRATIONS / "002_phase12_retention.sql").read_text()
    core = (MIGRATIONS / "001_phase12_core.sql").read_text()

    assert "set_config('app.system_maintenance', 'on', TRUE)" in sql
    assert "current_setting('app.system_maintenance', TRUE) = 'on'" in core


def test_seed_contains_exact_channel_to_business_mappings() -> None:
    sql = (MIGRATIONS / "003_phase12_seed_businesses.sql").read_text()

    assert "'sim-wa-harvest', 'openwa-simulator', 'harvest-big-shop'" in sql
    assert "'sim-wa-amac', 'openwa-simulator', 'amac-enterprise'" in sql
    assert "'sim-wa-serahs', 'openwa-simulator', 'serahs-glow-lounge'" in sql


def test_runtime_integration_migration_uses_known_capabilities_and_revisions() -> None:
    sql = (MIGRATIONS / "004_runtime_profiles_and_integrations.sql").read_text()
    declared = set(re.findall(r"'([a-z]+\.[a-z_]+)'", sql))
    known = {capability.value for capability in Capability}

    assert "ADD COLUMN IF NOT EXISTS runtime_revision" in sql
    assert "ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE" in sql
    assert "ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb" in sql
    assert "CREATE TABLE IF NOT EXISTS business_integrations" in sql
    assert "provider TEXT NOT NULL DEFAULT 'google_apps_script'" in sql
    assert "api_version TEXT NOT NULL DEFAULT 'tradeflow.ntheemba.v1'" in sql
    assert "auth_reference TEXT NOT NULL DEFAULT ''" in sql
    assert "status TEXT NOT NULL DEFAULT 'active'" in sql
    assert declared
    assert declared <= known
    assert "'harvest-tradeflow-standard'" in sql
    assert "'serahs-tradeflow-custom'" in sql


def test_channel_scope_migration_enforces_platform_business_separation() -> None:
    sql = (MIGRATIONS / "006_channel_scope_and_platform_context.sql").read_text()
    assert "scope IN ('business', 'platform')" in sql
    assert "scope = 'business' AND business_id IS NOT NULL" in sql
    assert "scope = 'platform' AND business_id IS NULL" in sql
    assert "business_channels_exact_identity_uidx" in sql
    assert "business_channels_primary_platform_role_uidx" in sql
    assert "business_capabilities_no_platform_capability" in sql
    assert "capability_id <> 'marketplace'" in sql



def test_marketplace_participation_migration_keeps_marketplace_out_of_business_capabilities() -> None:
    sql = (MIGRATIONS / "007_marketplace_participation.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS marketplace_business_listings" in sql
    assert "discoverable = FALSE OR status = 'active'" in sql
    assert "capability_id NOT IN ('marketplace', 'platform.marketplace')" in sql


def test_marketplace_handoff_migration_preserves_safe_selection_snapshot() -> None:
    sql = (MIGRATIONS / "008_marketplace_handoff.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS marketplace_handoffs" in sql
    assert "source_channel_id" in sql
    assert "target_business_id" in sql
    assert "business_product_id" in sql
    assert "ncpc_product_id" in sql
    assert "ncpc_variant_id" in sql
    assert "selling_price_snapshot" in sql
    assert "integration_id" in sql
    assert "UNIQUE (search_id, result_id)" in sql
    assert "base_url" not in sql
    assert "auth_reference" not in sql


def test_marketplace_handoff_consumption_migration_is_explicit_and_auditable() -> None:
    sql = (MIGRATIONS / "009_marketplace_handoff_consumption.sql").read_text()

    assert "ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ" in sql
    assert "status = 'ready' AND consumed_at IS NULL" in sql
    assert "status = 'consumed' AND consumed_at IS NOT NULL" in sql
    assert "009_marketplace_handoff_consumption" in sql


def test_runtime_security_migration_hardens_cross_tenant_and_secret_boundaries() -> None:
    sql = (MIGRATIONS / "010_runtime_security_hardening.sql").read_text()

    assert "business_channels_canonical_identity" in sql
    assert "business_integrations_auth_reference_is_reference" in sql
    assert "business_integrations_no_top_level_secret_values" in sql
    assert "business_integrations_public_https_endpoint" in sql
    assert "marketplace_handoffs_integration_tenant_fk" in sql
    assert "enforce_marketplace_handoff_source_channel" in sql
    assert "channel_scope IS DISTINCT FROM 'platform'" in sql
    assert "channel_role IS DISTINCT FROM 'marketplace'" in sql
    assert "010_runtime_security_hardening" in sql
