"""Test media upload to catalog-inventory."""
import httpx
import io
import time
from datetime import datetime

# Get existing product
print("Checking existing products...")
result = httpx.get(
    "http://localhost:8520/inventory/5181949d-729e-4d2c-8827-5fe6265f3052",
    timeout=30
)

if result.status_code == 404:
    print("Getting first product from database...")
    import subprocess
    result = subprocess.run([
        "docker", "exec", "soft-launch-postgres-1",
        "psql", "-U", "postgres", "-d", "ntheemba",
        "-c", "SELECT id FROM catalog_inventory.products LIMIT 1;"
    ], capture_output=True, text=True)
    print(result.stdout)

# Use a known product ID from bulk test
product_id = "6817e2fb-1b6e-4f90-9049-9e68887c1a1a"
business_id = "5181949d-729e-4d2c-8827-5fe6265f3052"

# Get auth token
print("\n1. Getting auth token...")
username = f"media_test_{int(time.time())}"
email = f"{username}@example.com"

reg_resp = httpx.post("http://localhost:8500/auth/register", json={
    "username": username,
    "email": email,
    "password": "Test@12345",
    "phone": "+260970000001",
}, timeout=30)
print(f"   Register: {reg_resp.status_code}")

login_resp = httpx.post("http://localhost:8500/auth/login", json={
    "identifier": username,
    "password": "Test@12345",
}, timeout=30)
login_resp.raise_for_status()
token = login_resp.json()["access_token"]
print(f"   ✓ Token: {token[:30]}...")

# Create simple test image (1x1 PNG)
print("\n2. Creating test image...")
png_bytes = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001"
    "0806000000001f15c4890000000a49444154787863f8cfcf"
    "0f000501010001184ea30a0000000049454e44ae426082"
)
print(f"   ✓ Test PNG: {len(png_bytes)} bytes")

# Upload media
print(f"\n3. Uploading image to product {product_id[:8]}...")
headers = {"Authorization": f"Bearer {token}"}
files = {"file": ("test-image.png", io.BytesIO(png_bytes), "image/png")}

try:
    upload_resp = httpx.post(
        f"http://localhost:8520/catalog/product/{product_id}/media",
        headers=headers,
        files=files,
        timeout=30
    )
    print(f"   Status: {upload_resp.status_code}")
    print(f"   Response: {upload_resp.text[:200]}")
    
    if upload_resp.status_code == 200:
        data = upload_resp.json()
        print(f"\n   ✅ Upload successful!")
        print(f"   URL: {data.get('url', 'N/A')}")
        print(f"   Filename: {data.get('filename')}")
        print(f"   Uploaded at: {data.get('uploaded_at')}")
    else:
        print(f"\n   ⚠️ Upload returned {upload_resp.status_code}")
        
except Exception as e:
    print(f"\n   ❌ Error: {e}")
    print(f"   (This is expected if Nextcloud isn't ready)")

# Check audit logs
print("\n4. Checking audit logs...")
time.sleep(2)
import subprocess
result = subprocess.run([
    "docker", "exec", "soft-launch-postgres-1",
    "psql", "-U", "postgres", "-d", "ntheemba",
    "-c", "SELECT event_type, payload->>'filename' as filename, created_at FROM audit_service.audit_logs WHERE service = 'catalog-inventory' AND event_type = 'media_uploaded' ORDER BY created_at DESC LIMIT 3;"
], capture_output=True, text=True)
print(result.stdout)

print("\n" + "="*60)
print("Media upload test complete!")
print("="*60)
