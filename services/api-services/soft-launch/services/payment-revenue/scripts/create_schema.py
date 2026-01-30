import os
import sys
from urllib.parse import urlparse
import psycopg2

DB_URL = "postgresql://postgres:!ladybug!%23!@127.0.0.1:5432/ntheemba"

def main():
    # parse URL to connection params
    parsed = urlparse(DB_URL)
    user = parsed.username
    password = parsed.password
    host = parsed.hostname or '127.0.0.1'
    port = parsed.port or 5432
    dbname = parsed.path.lstrip('/')

    conn = None
    # try a few password variants (percent-encoded vs literal) and env overrides
    candidates = []
    env_pw = os.environ.get('PG_PASSWORD') or os.environ.get('POSTGRES_PASSWORD')
    if env_pw:
        candidates.append(env_pw)
    if password:
        candidates.append(password)
        candidates.append(password.replace('%23', '#'))

    last_err = None
    for pw in candidates:
        try:
            conn = psycopg2.connect(user=user, password=pw, host=host, port=port, dbname=dbname)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute('CREATE SCHEMA IF NOT EXISTS payment_revenue')
            print('Schema `payment_revenue` ensured (used password candidate)')
            cur.close()
            last_err = None
            break
        except Exception as e:
            last_err = e

    if last_err:
        print('Failed to create schema, tried candidates. Last error:', repr(last_err))
        if conn:
            conn.close()
        sys.exit(2)

    if conn:
        conn.close()

if __name__ == '__main__':
    main()
