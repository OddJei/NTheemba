from pathlib import Path
from dotenv import load_dotenv
import os
import sys

repo_root = Path(__file__).resolve().parent.parent
env_path = repo_root / 'config' / '.env'
if env_path.exists():
    load_dotenv(env_path)

PG_USER = os.getenv('PG_USER')
PG_PASS = os.getenv('PG_PASSWORD')
PG_DB = os.getenv('PG_DB')
PG_HOST = os.getenv('PG_HOST', 'localhost')

if not (PG_USER and PG_PASS and PG_DB):
    print('Missing PG_USER/PG_PASSWORD/PG_DB in env (check config/.env).')
    sys.exit(1)

# Strip any surrounding quotes from password
PG_PASS = PG_PASS.strip('"').strip("'")

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except Exception as e:
    print('psycopg2 not available in the venv. Install with: pip install psycopg2-binary')
    raise

print(f'Connecting to Postgres host={PG_HOST} user={PG_USER} to ensure database "{PG_DB}" exists...')
conn = psycopg2.connect(dbname='postgres', user=PG_USER, password=PG_PASS, host=PG_HOST)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (PG_DB,))
if cur.fetchone():
    print(f'Database "{PG_DB}" already exists.')
else:
    print(f'Creating database "{PG_DB}"...')
    cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(PG_DB)))
    print('Created.')
cur.close()
conn.close()
