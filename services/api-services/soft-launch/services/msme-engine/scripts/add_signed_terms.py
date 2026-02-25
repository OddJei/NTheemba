import sqlite3, os
path = os.path.join('services','msme-engine','msme_engine.db')
print('DB PATH', path, 'exists=', os.path.exists(path))
if not os.path.exists(path):
    print('DB not found; nothing to migrate')
else:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        print('users columns:', cols)
        if 'signed_terms' not in cols:
            print('Adding signed_terms column')
            cur.execute("ALTER TABLE users ADD COLUMN signed_terms INTEGER DEFAULT 0")
            conn.commit()
            print('Column added')
        else:
            print('Column already present')
    finally:
        conn.close()
