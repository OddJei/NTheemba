from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import text

from alembic import context

# Add the src directory to sys.path so we can import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.db import Base
from src.app.config import get_database_url
from src.app.models import (
    Settlement,
    Outbox,
    Payout,
    SubscriptionPayment,
    IdempotencyRecord,
    PawaPayDeposit,
    PawaPayPayout,
    PawaPayRefund,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set the database URL from config
# Escape percent signs to avoid ConfigParser interpolation errors when
# the DB password contains percent-encoded characters (e.g. "%23").
raw_url = get_database_url()
safe_url = raw_url.replace('%', '%%') if raw_url else raw_url
config.set_main_option("sqlalchemy.url", safe_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url().replace("+aiosqlite", "").replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="payment_revenue",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Convert async URL to sync for migrations
    db_url = get_database_url().replace("+aiosqlite", "").replace("+asyncpg", "")
    
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = db_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # ensure we are operating inside the payment_revenue schema
        try:
            connection.execute(text("SET search_path TO payment_revenue"))
        except Exception:
            # best-effort: if setting search_path fails, migrations may still run
            pass

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="payment_revenue",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
