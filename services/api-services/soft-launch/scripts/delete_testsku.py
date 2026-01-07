import sqlite3
DB=r"C:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch\services\catalog-inventory\catalog_inventory.db"
conn=sqlite3.connect(DB)
cur=conn.cursor()
cur.execute("SELECT id,product_id FROM product_variants WHERE sku='TESTSKU'")
rows=cur.fetchall()
print('found', len(rows))
for vid, pid in rows:
    cur.execute("DELETE FROM inventory WHERE variant_id=?", (vid,))
    cur.execute("DELETE FROM product_variants WHERE id=?", (vid,))
    # optionally remove product if no other variants
    cur.execute("SELECT COUNT(*) FROM product_variants WHERE product_id=?", (pid,))
    if cur.fetchone()[0]==0:
        cur.execute("DELETE FROM products WHERE id=?", (pid,))
conn.commit()
print('deleted')
conn.close()
