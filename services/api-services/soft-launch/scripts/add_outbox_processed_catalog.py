import sqlite3
from pathlib import Path

DB = Path(r"c:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch\services\catalog-inventory\catalog_inventory.db")
if not DB.exists():
    print('catalog_inventory.db not found at', DB)
    raise SystemExit(1)

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("PRAGMA table_info(outbox_events)")
cols = [r[1] for r in cur.fetchall()]
if 'processed' in cols:
    print('processed column already present')
else:
    print('adding processed column to outbox_events')
    cur.execute("ALTER TABLE outbox_events ADD COLUMN processed INTEGER DEFAULT 0")
    conn.commit()
    print('done')
conn.close()
