#!/usr/bin/env python3
"""Local SQLite migration helper for dev: ensure expected columns exist.

Usage: python migrate_local_sqlite.py
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), '..', 'msme_engine.db')
DB = os.path.normpath(DB)

def ensure_column(conn, table, column, sql_type='INTEGER'):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column in cols:
        print(f"{table}.{column} already present")
        return False
    print(f"Adding column {table}.{column} {sql_type}")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
    conn.commit()
    return True

def main():
    print('DB PATH', DB, 'exists=', os.path.exists(DB))
    if not os.path.exists(DB):
        print('DB not found, aborting')
        return
    conn = sqlite3.connect(DB)
    try:
        ensure_column(conn, 'users', 'signed_terms', 'INTEGER DEFAULT 0')
    except Exception as e:
        print('failed to alter users:', e)
    try:
        ensure_column(conn, 'businesses', 'affiliate_id', 'TEXT')
    except Exception as e:
        print('failed to alter businesses.affiliate_id:', e)
    conn.close()

if __name__ == '__main__':
    main()
