from dotenv import load_dotenv
from pathlib import Path
import os
import psycopg2

repo_root = Path(__file__).resolve().parent.parent
env_path = repo_root / 'config' / '.env'
if env_path.exists():
    load_dotenv(env_path)

PG_USER = os.getenv('PG_USER')
PG_PASS = os.getenv('PG_PASSWORD')
PG_DB = os.getenv('PG_DB')
PG_HOST = os.getenv('PG_HOST', 'localhost')

PG_PASS = PG_PASS.strip('"').strip("'") if PG_PASS else PG_PASS

SERVICE_SCHEMA = os.getenv('SERVICE_SCHEMA', os.getenv('AUDIT_SCHEMA', 'audit_service'))

conn = psycopg2.connect(dbname=PG_DB, user=PG_USER, password=PG_PASS, host=PG_HOST)
cur = conn.cursor()
cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = %s", (SERVICE_SCHEMA,))
rows = cur.fetchall()
print(f'tables in {SERVICE_SCHEMA} schema:')
for r in rows:
    print('-', r[1])
cur.close()
conn.close()
