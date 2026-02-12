#!/usr/bin/env python3
"""
Verify that affiliate attribution was created with affiliate_id
"""
import sqlite3
import json
from datetime import datetime, timedelta

# Connect to the affiliate-engine database
conn = sqlite3.connect("/tmp/affiliate_engine.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\n" + "="*60)
print("Verifying Affiliate Attribution")
print("="*60)

# Get recent attributions (last 5 minutes)
cutoff = (datetime.now() - timedelta(minutes=5)).isoformat()

try:
    cursor.execute("""
        SELECT id, order_id, affiliate_code, affiliate_id, amount_minor, created_at
        FROM affiliate_attributions
        WHERE created_at > ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (cutoff,))
    
    rows = cursor.fetchall()
    
    if not rows:
        print("\n[NO RECENT ATTRIBUTIONS FOUND]")
        print(f"Search window: {cutoff} to now")
        
        # Show all attributions
        print("\n[ALL ATTRIBUTIONS IN DATABASE]")
        cursor.execute("""
            SELECT id, order_id, affiliate_code, affiliate_id, amount_minor, created_at
            FROM affiliate_attributions
            ORDER BY created_at DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  Order: {row['order_id']}")
                print(f"    Affiliate ID: {row['affiliate_id']}")
                print(f"    Affiliate Code: {row['affiliate_code']}")
                print(f"    Amount: {row['amount_minor']}")
                print(f"    Created: {row['created_at']}")
                print()
        else:
            print("  [Database is empty]")
    else:
        print(f"\n[FOUND {len(rows)} RECENT ATTRIBUTIONS]")
        for row in rows:
            print(f"\nOrder ID: {row['order_id']}")
            print(f"  Affiliate ID: {row['affiliate_id']}")
            print(f"  Affiliate Code: {row['affiliate_code']}")
            print(f"  Amount (minor): {row['amount_minor']}")
            print(f"  Created At: {row['created_at']}")
            
            if row['affiliate_id'] == 'aff-xyz-789':
                print("  >> SUCCESS: Affiliate ID correctly extracted and stored!")
            
except Exception as e:
    print(f"\n[ERROR] Could not query database: {e}")
    print("  Make sure the affiliate-engine container is running")

finally:
    conn.close()

print("\n" + "="*60)
