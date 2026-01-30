import os
import sys
import sqlite3
import json
from urllib.parse import urlparse
import psycopg2
import psycopg2.extras

SQLITE_PATH = os.path.join(os.path.dirname(__file__), '..', 'payment_revenue.db')
DB_URL = "postgresql://postgres:!ladybug!%23!@127.0.0.1:5432/ntheemba"

def load_sqlite_rows():
    db_path = os.path.abspath(SQLITE_PATH)
    if not os.path.exists(db_path):
        print('SQLite DB not found at', db_path)
        sys.exit(1)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        cur.execute('SELECT * FROM outbox')
    except Exception as e:
        print('Failed reading sqlite outbox:', repr(e))
        sys.exit(2)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    con.close()
    # payload is stored as JSON text in sqlite; parse it
    for r in rows:
        try:
            r['payload'] = json.loads(r.get('payload') or '{}')
        except Exception:
            r['payload'] = {}
    return rows

def connect_postgres():
    parsed = urlparse(DB_URL)
    user = parsed.username
    password = parsed.password.replace('%23', '#') if parsed.password else None
    host = parsed.hostname
    port = parsed.port
    dbname = parsed.path.lstrip('/')
    conn = psycopg2.connect(user=user, password=password, host=host, port=port, dbname=dbname)
    return conn

def ensure_table(conn):
    ddl = '''
    CREATE TABLE IF NOT EXISTS payment_revenue.outbox (
        id VARCHAR(36) PRIMARY KEY,
        topic VARCHAR(64) NOT NULL,
        destination VARCHAR(256) NOT NULL,
        payload JSONB NOT NULL,
        status VARCHAR(32) NOT NULL,
        attempts INTEGER NOT NULL,
        last_error VARCHAR(512),
        send_after TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    '''
    cur = conn.cursor()
    cur.execute(ddl)
    cur.execute('CREATE INDEX IF NOT EXISTS ix_outbox_topic ON payment_revenue.outbox (topic)')
    conn.commit()
    cur.close()

def insert_rows(conn, rows):
    cur = conn.cursor()
    inserted = 0
    for r in rows:
        try:
            cur.execute('''
            INSERT INTO payment_revenue.outbox (id, topic, destination, payload, status, attempts, last_error, send_after, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
            ''', (
                r.get('id'), r.get('topic'), r.get('destination'), psycopg2.extras.Json(r.get('payload')),
                r.get('status'), r.get('attempts'), r.get('last_error'), r.get('send_after'), r.get('created_at'), r.get('updated_at')
            ))
            inserted += cur.rowcount
        except Exception as e:
            print('Failed inserting row', r.get('id'), repr(e))
    conn.commit()
    cur.close()
    return inserted

def main():
    rows = load_sqlite_rows()
    print('Found', len(rows), 'rows in sqlite outbox')
    if not rows:
        return
    conn = connect_postgres()
    ensure_table(conn)
    inserted = insert_rows(conn, rows)
    print('Inserted', inserted, 'rows into Postgres outbox')
    conn.close()

if __name__ == '__main__':
    main()
