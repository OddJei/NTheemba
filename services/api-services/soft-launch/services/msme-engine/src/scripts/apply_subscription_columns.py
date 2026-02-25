import os
import sys

DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@127.0.0.1:5432/ntheemba')

SQL = '''
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'subscription_price_minor'
    ) THEN
        ALTER TABLE msme_engine.businesses ADD COLUMN subscription_price_minor integer;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'msme_engine' AND table_name = 'businesses' AND column_name = 'subscription_currency'
    ) THEN
        ALTER TABLE msme_engine.businesses ADD COLUMN subscription_currency varchar(10);
    END IF;
END$$;
'''

print('Using DB_URL:', DB_URL)

try:
    import psycopg2
    import psycopg2.extras
except Exception as e:
    print('psycopg2 not available in venv:', e)
    sys.exit(1)

# Strip asyncpg prefix if present
if DB_URL.startswith('postgresql+asyncpg://'):
    dsn = DB_URL.replace('postgresql+asyncpg://', 'postgresql://', 1)
else:
    dsn = DB_URL

try:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(SQL)
    cur.close()
    conn.close()
    print('Applied subscription columns (if missing).')
except Exception as e:
    print('Failed to apply SQL:', e)
    sys.exit(2)
