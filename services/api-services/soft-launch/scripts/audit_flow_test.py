"""Comprehensive audit test - all catalog-inventory operations"""
import httpx
import uuid
import time
import subprocess

def run_sql(query):
    """Execute SQL and return result."""
    result = subprocess.run([
        "docker", "exec", "soft-launch-postgres-1",
        "psql", "-U", "postgres", "-d", "ntheemba", "-c", query
    ], capture_output=True, text=True)
    return result.stdout

# Setup
username = f"audit_full_test_{uuid.uuid4().hex[:8]}"
email = f"{username}@example.com"

print("="*70)
print("COMPREHENSIVE AUDIT EVENT TEST - Catalog-Inventory Service")
print("="*70)

# Register and login
print("\n1. Setting up test user...")
reg_resp = httpx.post("http://localhost:8500/auth/register", json={
    "username": username,
    "email": email,
    "password": "Test@12345",
    "phone": "+260970000001",
}, timeout=30)
reg_resp.raise_for_status()

login_resp = httpx.post("http://localhost:8500/auth/login", json={
    "identifier": username,
    "password": "Test@12345",
}, timeout=30)
login_resp.raise_for_status()
token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
business_id = "5181949d-729e-4d2c-8827-5fe6265f3052"
print(f"   ✓ Test user ready: {email}")

# Test 1: Category creation
print("\n2. Testing CATEGORY_CREATED audit event...")
cat_resp = httpx.post("http://localhost:8520/catalog/category", headers=headers, json={
    "business_id": business_id,
    "name": f"Audit Test Cat {int(time.time())}",
    "description": "Testing category audit"
}, timeout=30)
cat_resp.raise_for_status()
category_id = cat_resp.json()["id"]
print(f"   ✓ Category created: {category_id}")
time.sleep(1)

# Test 2: Product creation
print("\n3. Testing PRODUCT_CREATED audit event...")
prod_resp = httpx.post("http://localhost:8520/catalog/product", headers=headers, json={
    "business_id": business_id,
    "category_id": category_id,
    "name": f"Audit Test Product {int(time.time())}",
    "description": "Testing product audit",
    "price": 10000,
    "tags": ["test", "audit"]
}, timeout=30)
prod_resp.raise_for_status()
product_id = prod_resp.json()["id"]
print(f"   ✓ Product created: {product_id}")
time.sleep(1)

# Test 3: Variant creation
print("\n4. Testing VARIANT_CREATED audit event...")
variant_resp = httpx.post(f"http://localhost:8520/catalog/product/{product_id}/variant", headers=headers, json={
    "sku": f"AUDIT-SKU-{uuid.uuid4().hex[:8].upper()}",
    "name": "Standard",
    "price_override": 10000
}, timeout=30)
variant_resp.raise_for_status()
variant_id = variant_resp.json()["id"]
print(f"   ✓ Variant created: {variant_id}")
time.sleep(1)

# Test 4: Inventory update
print("\n5. Testing INVENTORY_UPDATED audit event...")
inv_resp = httpx.post("http://localhost:8520/inventory/update", headers=headers, json={
    "variant_id": variant_id,
    "delta": 50,
    "reason": "Testing inventory audit"
}, timeout=30)
inv_resp.raise_for_status()
print(f"   ✓ Inventory updated")
time.sleep(2)

# Verify all audit events
print("\n" + "="*70)
print("AUDIT EVENT VERIFICATION")
print("="*70)

query = """
SELECT 
    event_type,
    payload->>'category_id' as category_id,
    payload->>'product_id' as product_id,
    payload->>'variant_id' as variant_id,
    created_at
FROM audit_service.audit_logs 
WHERE service = 'catalog-inventory' 
  AND event_type IN ('category_created', 'product_created', 'variant_created', 'inventory_updated')
ORDER BY created_at DESC 
LIMIT 10;
"""

print("\nRecent catalog-inventory audit events:")
print(run_sql(query))

# Summary count by event type
print("\nEvent type summary (last 5 minutes):")
summary_query = """
SELECT 
    event_type, 
    COUNT(*) as count
FROM audit_service.audit_logs 
WHERE service = 'catalog-inventory' 
  AND created_at > NOW() - INTERVAL '5 minutes'
GROUP BY event_type
ORDER BY count DESC;
"""
print(run_sql(summary_query))

print("\n" + "="*70)
print("✅ COMPREHENSIVE AUDIT TEST COMPLETE!")
print("="*70)
print(f"""
Test Results:
  - Category ID:  {category_id}
  - Product ID:   {product_id}
  - Variant ID:   {variant_id}
  
All 4 audit event types should be visible above:
  ✓ category_created
  ✓ product_created
  ✓ variant_created
  ✓ inventory_updated
""")
