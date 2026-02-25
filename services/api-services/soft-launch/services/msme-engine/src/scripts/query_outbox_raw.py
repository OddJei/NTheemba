import os
import json
from sqlalchemy import create_engine, text

DB_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:!ladybug!#!@127.0.0.1:5432/ntheemba')
engine = create_engine(DB_URL)

with engine.connect() as conn:
    sql = text('SELECT id, topic, destination, target, payload, headers, last_response, status, attempts, created_at FROM msme_engine.outbox_events ORDER BY created_at DESC LIMIT 20')
    res = conn.execute(sql)
    rows = res.fetchall()
    out = []
    for r in rows:
        row = {
            'id': str(r[0]),
            'topic': r[1],
            'destination': r[2],
            'target': r[3],
            'payload': r[4],
            'headers': r[5],
            'last_response': r[6],
            'status': r[7],
            'attempts': r[8],
            'created_at': str(r[9]) if r[9] is not None else None,
        }
        out.append(row)
    print(json.dumps(out, indent=2, default=str))
