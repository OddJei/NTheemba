import os
import sys
import uuid
import json

DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@127.0.0.1:5432/ntheemba')

import sys
if len(sys.argv) > 1:
    # Allow passing DB URL as first CLI arg to avoid shell quoting issues
    DB_URL = sys.argv[1]

# Normalize common scheme and percent-encode credentials to avoid libpq parsing errors
try:
    from urllib.parse import urlparse, urlunparse, quote
    if DB_URL.startswith('postgresql+psycopg2://'):
        DB_URL = DB_URL.replace('postgresql+psycopg2://', 'postgresql://', 1)
    # Manually extract and encode credentials (handles '#' and '!' in passwords)
    if '://' in DB_URL:
        scheme, rest = DB_URL.split('://', 1)
        if '@' in rest:
            creds, host_rest = rest.split('@', 1)
            if ':' in creds:
                user, pwd = creds.split(':', 1)
                user_enc = quote(user)
                pwd_enc = quote(pwd)
                DB_URL = f"{scheme}://{user_enc}:{pwd_enc}@{host_rest}"
    # Final parse to ensure form
    parsed = urlparse(DB_URL)
    if parsed.username or parsed.password:
        user = quote(parsed.username or '')
        pwd = quote(parsed.password or '')
        netloc = f"{user}:{pwd}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        DB_URL = urlunparse((parsed.scheme, netloc, parsed.path or '', parsed.params or '', parsed.query or '', parsed.fragment or ''))
except Exception:
    pass

SQL = '''
INSERT INTO msme_engine.outbox_events
  (id, topic, payload, status, attempts, correlation_id, dedupe_key, created_at, updated_at)
VALUES
  (%s, %s, %s::jsonb, %s, %s, %s, %s, now(), now())
RETURNING id;
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

payload = {"event": "direct_psql_test", "ts": __import__('datetime').datetime.utcnow().isoformat()}
new_id = str(uuid.uuid4())
topic = 'test.direct.psql'
status = 'pending'
attempts = 0
correlation_id = str(uuid.uuid4())
dedupe = f"direct-psql-{new_id}"

try:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(SQL, (new_id, topic, json.dumps(payload), status, attempts, correlation_id, dedupe))
    row = cur.fetchone()
    cur.close()
    conn.close()
    print('Inserted outbox id:', row[0])
except Exception as e:
    print('Failed to insert outbox row:', e)
    sys.exit(2)
