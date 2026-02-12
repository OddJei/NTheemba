"""Quick test: Register user -> Create category -> Check audit log"""
import httpx
import uuid
import time

# Register new user
username = f"audit_test_{uuid.uuid4().hex[:8]}"
email = f"{username}@example.com"

print(f"1. Registering user: {email}")
reg_resp = httpx.post("http://localhost:8500/auth/register", json={
    "username": username,
    "email": email,
    "password": "Test@12345",
    "phone": "+260970000001",
}, timeout=30)
reg_resp.raise_for_status()
print(f"   ✓ User registered")

# Login to get token
print("   Logging in...")
login_resp = httpx.post("http://localhost:8500/auth/login", json={
    "identifier": username,
    "password": "Test@12345",
}, timeout=30)
login_resp.raise_for_status()
token = login_resp.json()["access_token"]
print(f"   ✓ Got token")

# Use existing business ID from database (we know business_id=1 exists)
business_id = "5181949d-729e-4d2c-8827-5fe6265f3052"  # From earlier bulk script

# Create category
print("\n2. Creating category...")
cat_resp = httpx.post("http://localhost:8520/catalog/category", headers={
    "Authorization": f"Bearer {token}"
}, json={
    "business_id": business_id,
    "name": f"Audit Test Category {int(time.time())}",
    "description": "Testing audit logging"
}, timeout=30)
print(f"   Response status: {cat_resp.status_code}")
cat_resp.raise_for_status()
category = cat_resp.json()
print(f"   ✓ Category created: ID={category['id']}")

# Wait for async processing
time.sleep(2)

# Check audit log
print("\n3. Checking audit logs...")
import subprocess
result = subprocess.run([
    "docker", "exec", "soft-launch-postgres-1",
    "psql", "-U", "postgres", "-d", "ntheemba",
    "-c", f"SELECT event_type, payload->>'category_id' as cat_id, payload->>'name' as name, created_at FROM audit_service.audit_logs WHERE service = 'catalog-inventory' AND event_type = 'category_created' ORDER BY created_at DESC LIMIT 3;"
], capture_output=True, text=True)
print(result.stdout)

print("\n✅ TEST COMPLETE!")
print(f"   Created category {category['id']} for business {business_id}")
print(f"   Check audit_service.audit_logs for event_type='category_created'")
