from pathlib import Path


COMPOSE = Path("../../../docker-compose.yml")


def _compose_text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def test_compose_applies_ntheemba_migrations_before_api_start() -> None:
    text = _compose_text()

    assert "ntheemba-migrate:" in text
    assert 'restart: "no"' in text
    assert "scripts/migrate_postgres.py" in text
    assert "condition: service_completed_successfully" in text


def test_compose_worker_is_explicit_and_requires_https_ncpc_configuration() -> None:
    text = _compose_text()

    assert "ntheemba-worker:" in text
    assert 'profiles: ["ntheemba-worker", "acceptance"]' in text
    assert 'command: ["ntheemba-inbound-worker"]' in text
    assert "NTHEEMBA_NCPC_BASE_URL:" in text
    assert "NTHEEMBA_NCPC_API_TOKEN:" in text
