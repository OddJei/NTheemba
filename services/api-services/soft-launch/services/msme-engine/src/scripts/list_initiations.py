import os
import json
from sqlalchemy import create_engine, text

url = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:!ladybug!#!@127.0.0.1:5432/ntheemba')
print('DB URL (masked):', url[:30]+'...')
engine = create_engine(url)
with engine.connect() as conn:
    r = conn.execute(text('SELECT id, deposit_id, business_id, affiliate_id, metadata, status, created_at FROM msme_engine.payment_initiations ORDER BY created_at DESC LIMIT 20'))
    rows = [dict(id=str(row[0]), deposit_id=row[1], business_id=row[2], affiliate_id=row[3], metadata=(row[4] if row[4] else {}), status=row[5], created_at=str(row[6])) for row in r]
    print(json.dumps(rows, indent=2))
