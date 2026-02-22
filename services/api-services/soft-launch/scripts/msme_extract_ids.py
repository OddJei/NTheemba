#!/usr/bin/env python3
"""Extract businesses and affiliates from msme_engine.db (SQLite).
Writes JSON list to scripts/msme_ids.json
"""
import sqlite3
import json
from pathlib import Path

DB = Path("services/msme-engine/msme_engine.db")
OUT = Path("scripts/msme_ids.json")

def main():
    if not DB.exists():
        print("DB not found:", DB)
        raise SystemExit(2)
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    res = {}
    try:
        cur.execute("SELECT id, name, affiliate_code FROM businesses LIMIT 50")
        rows = cur.fetchall()
        res['businesses'] = [{"id": r[0], "name": r[1], "affiliate_code": r[2]} for r in rows]
    except Exception as e:
        res['businesses_error'] = str(e)

    try:
        cur.execute("SELECT id, username, phone, affiliate_id, business_id FROM users WHERE affiliate_id IS NOT NULL LIMIT 50")
        rows = cur.fetchall()
        res['affiliate_users'] = [{"id": r[0], "username": r[1], "phone": r[2], "affiliate_id": r[3], "business_id": r[4]} for r in rows]
    except Exception as e:
        res['affiliate_users_error'] = str(e)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding='utf-8')
    print("WROTE", OUT)

if __name__ == '__main__':
    main()
