import sqlite3
import uuid
from datetime import datetime, timezone

DB = r"c:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch\services\msme-engine\msme_engine.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Ensure there's at least one role, pick one
cur.execute("SELECT id FROM roles LIMIT 1")
row = cur.fetchone()
if row:
    role_id = row[0]
else:
    # create a default role
    role_id = str(uuid.uuid4())
    cur.execute("INSERT INTO roles (id, name, description, created_at) VALUES (?, ?, ?, ?)", (role_id, 'default', 'default role', datetime.now(timezone.utc).isoformat()))

# create a user to own the business
user_id = str(uuid.uuid4())
cur.execute("INSERT OR IGNORE INTO users (id, username, email, phone, password_hash, role_id, business_id, affiliate_id, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
    user_id,
    'test_owner',
    'owner@example.local',
    '+0000000000',
    'passwordhash',
    role_id,
    None,
    None,
    1,
    datetime.now(timezone.utc).isoformat(),
    datetime.now(timezone.utc).isoformat(),
))

# insert business with id 'test-business'
business_id = 'test-business'
cur.execute("INSERT OR REPLACE INTO businesses (id, name, owner_id, location, category, logo_url, affiliate_code, referred_by_msme_code, subscription_plan, subscription_expiry, delivery_locations, tags, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
    business_id,
    'Test Business',
    user_id,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    1,
    datetime.now(timezone.utc).isoformat(),
    datetime.now(timezone.utc).isoformat(),
))

conn.commit()
conn.close()
print('inserted test business and owner')
