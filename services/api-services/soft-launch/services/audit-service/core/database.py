import os
# Load environment from .env early so this module can see DB settings when
# other modules import `core.database` before `config.settings` is imported.
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
# Prefer a project-local `config/.env` (this repo stores env under `config/.env`).
repo_root = Path(__file__).resolve().parent.parent
env_path = repo_root / 'config' / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fall back to searching upward for a .env
    found = find_dotenv()
    if found:
        load_dotenv(found)

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base

# Build DATABASE_URL from environment. Prefer AUDIT_DATABASE_URL if provided,
# otherwise require PG_USER/PG_PASSWORD/PG_DB/PG_HOST to be set for Postgres.
DATABASE_URL = os.getenv('AUDIT_DATABASE_URL')
if not DATABASE_URL:
    pg_user = os.getenv('PG_USER')
    pg_pass = os.getenv('PG_PASSWORD')
    pg_db = os.getenv('PG_DB')
    pg_host = os.getenv('PG_HOST')
    if pg_user and pg_pass and pg_db and pg_host:
        # Postgres URL. URL-encode password to handle special characters and strip surrounding quotes.
        from urllib.parse import quote_plus
        pg_pass_quoted = quote_plus(pg_pass.strip('"'))
        DATABASE_URL = f"postgresql://{pg_user}:{pg_pass_quoted}@{pg_host}/{pg_db}"
    else:
        raise RuntimeError(
            'No database configured. Set AUDIT_DATABASE_URL or PG_USER/PG_PASSWORD/PG_DB/PG_HOST environment variables to connect to Postgres.'
        )

engine = create_engine(DATABASE_URL)

# Allow per-service schemas. Default to 'audit_service' for this service.
SERVICE_SCHEMA = os.getenv('SERVICE_SCHEMA', os.getenv('AUDIT_SCHEMA', 'audit_service'))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Use a MetaData object with a default schema so models without explicit schema
# will be created inside the service-specific schema.
metadata = MetaData(schema=SERVICE_SCHEMA)
Base = declarative_base(metadata=metadata)


def init_db():
    # Import models here to register with Base and create tables if missing.
    try:
        import models.audit  # noqa: F401
    except Exception:
        pass
    # Ensure the `audit_service` schema exists in Postgres before creating tables
    try:
        from sqlalchemy import text
        # Ensure the CREATE SCHEMA runs outside a transactional context on Postgres
        with engine.connect() as conn:
            autocommit_conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            autocommit_conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {SERVICE_SCHEMA}'))
    except Exception:
        # If the DB doesn't support CREATE SCHEMA (e.g., sqlite), ignore the step.
        pass

    Base.metadata.create_all(bind=engine)
