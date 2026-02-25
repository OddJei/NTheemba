import os
import json
from sqlalchemy import create_engine, text

DB_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:!ladybug!#!@127.0.0.1:5432/ntheemba')
engine = create_engine(DB_URL)

with engine.connect() as conn:
    sql = text("SELECT id, topic, destination, payload, created_at FROM msme_engine.outbox_events WHERE topic LIKE 'notification.%' ORDER BY created_at DESC LIMIT 50")
    res = conn.execute(sql)
    rows = res.fetchall()
    out = []
    for r in rows:
        out.append({
            'id': str(r[0]),
            'topic': r[1],
            'destination': r[2],
            'payload': r[3],
            'created_at': str(r[4]) if r[4] is not None else None,
        })
    print(json.dumps(out, indent=2, default=str))
