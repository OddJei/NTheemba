import psycopg2
from urllib.parse import urlparse

DB_URL = "postgresql://postgres:!ladybug!%23!@127.0.0.1:5432/ntheemba"

def main():
    parsed = urlparse(DB_URL)
    user = parsed.username
    password = parsed.password.replace('%23', '#') if parsed.password else None
    host = parsed.hostname
    port = parsed.port
    dbname = parsed.path.lstrip('/')

    conn = psycopg2.connect(user=user, password=password, host=host, port=port, dbname=dbname)
    cur = conn.cursor()
    try:
        cur.execute("SELECT version_num FROM public.alembic_version")
        print('alembic_version (public):', cur.fetchone()[0])
    except Exception:
        print('alembic_version table not present in public')
    cur.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname in ('payment_revenue','public') ORDER BY schemaname, tablename")
    rows = cur.fetchall()
    print('tables:')
    for s, t in rows:
        print(f" - {s}.{t}")

    # try to count if outbox exists in either schema
    found = False
    for s, t in rows:
        if t == 'outbox':
            cur.execute(f"SELECT count(*) FROM {s}.outbox")
            cnt = cur.fetchone()[0]
            print(f'outbox count in {s}:', cnt)
            found = True
    if not found:
        print('outbox table not found in payment_revenue or public')
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
