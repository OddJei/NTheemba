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

PG_PASS = PG_PASS.strip('"').strip("'")

try:
    import psycopg2
except Exception as e:
    print('psycopg2 not available. Install in venv: pip install psycopg2-binary')
    raise

conn = psycopg2.connect(dbname=PG_DB, user=PG_USER, password=PG_PASS, host=PG_HOST)
conn.autocommit = True
cur = conn.cursor()

SERVICE_SCHEMA = os.getenv('SERVICE_SCHEMA', os.getenv('AUDIT_SCHEMA', 'audit_service'))

# Find where audit_logs currently lives
cur.execute("SELECT table_schema FROM information_schema.tables WHERE table_name='audit_logs';")
rows = cur.fetchall()
if not rows:
    print('No table named audit_logs found in the database.')
    cur.close()
    conn.close()
    sys.exit(0)

schemas = sorted({r[0] for r in rows})
print('Found audit_logs in schemas:', schemas)

if SERVICE_SCHEMA in schemas and len(schemas) == 1:
    print(f'audit_logs already in {SERVICE_SCHEMA} schema — nothing to do.')
    cur.close()
    conn.close()
    sys.exit(0)

# If the table exists in multiple schemas (unlikely), prioritize moving from public if present
source_schema = None
if 'public' in schemas:
    source_schema = 'public'
else:
    # pick first schema that is not audit_service
    for s in schemas:
        if s != 'audit_service':
            source_schema = s
            break

if not source_schema:
    print('Could not determine a source schema to move from. Schemas:', schemas)
    cur.close()
    conn.close()
    sys.exit(1)

try:
    # Ensure target schema exists
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SERVICE_SCHEMA}")
    # Move the table
    # If the target already contains a table with the same name, merge rows and drop source.
    cur.execute("SELECT to_regclass(%s)", (f'{SERVICE_SCHEMA}.audit_logs',))
    target_exists = cur.fetchone()[0] is not None

    if not target_exists:
        cur.execute(f"ALTER TABLE {source_schema}.audit_logs SET SCHEMA {SERVICE_SCHEMA}")
        print(f'Successfully moved audit_logs to {SERVICE_SCHEMA} schema.')
    else:
        print(f'Target table {SERVICE_SCHEMA}.audit_logs already exists. Merging rows from {source_schema}...')
        # Count rows in source and target
        cur.execute("SELECT count(*) FROM {}.audit_logs".format(source_schema))
        src_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM {}.audit_logs".format(SERVICE_SCHEMA))
        tgt_count = cur.fetchone()[0]
        print(f'source rows={src_count}, target rows={tgt_count}')

        # Insert non-duplicated rows from source into target based on id
        cur.execute(
            "INSERT INTO {t}.audit_logs (id, occurred_at, service, event_type, actor_id, entity_type, entity_id, severity, payload, metadata, checksum, archived, created_at) "
            "SELECT id, occurred_at, service, event_type, actor_id, entity_type, entity_id, severity, payload, metadata, checksum, archived, created_at "
            "FROM {s}.audit_logs s WHERE NOT EXISTS (SELECT 1 FROM {t}.audit_logs t WHERE t.id = s.id)".format(s=source_schema, t=SERVICE_SCHEMA)
        )
        # After merging, drop the source table
        cur.execute(f"DROP TABLE {source_schema}.audit_logs")
        print(f'Merged rows and dropped {source_schema}.audit_logs')
except Exception as e:
    print('Error while moving table:', e)
    raise
finally:
    cur.close()
    conn.close()
