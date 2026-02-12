"""
Test catalog-inventory audit event emissions.
"""
import httpx
import json
import time
import sys

def get_auth_token():
    """Get JWT token from msme-engine."""
    print("Getting auth token...")
    try:
        login_response = httpx.post(
            "http://localhost:8500/auth/login",
            json={
                "identifier": "msme@example.com",
                "password": "password123"
            },
            timeout=30.0
        )
        print(f"Login response status: {login_response.status_code}")
        login_response.raise_for_status()
        token = login_response.json()["access_token"]
        print(f"✓ Got token: {token[:20]}...")
        return token
    except Exception as e:
        print(f"❌ Failed to get token: {e}")
        raise

def test_category_creation():
    """Create a category and verify audit event."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create category
    category_payload = {
        "business_id": 1,
        "name": f"Test Audit Category {int(time.time())}",
        "parent_id": None,
        "description": "Testing audit event emission"
    }
    
    print(f"\nCreating category: {category_payload['name']}")
    try:
        cat_response = httpx.post(
            "http://localhost:8520/catalog/category",
            json=category_payload,
            headers=headers,
            timeout=30.0
        )
        print(f"Category creation response status: {cat_response.status_code}")
        print(f"Response body: {cat_response.text[:200]}")
        cat_response.raise_for_status()
        cat_data = cat_response.json()
        print(f"✓ Category created: ID={cat_data.get('id')}")
        return cat_data.get('id')
    except Exception as e:
        print(f"❌ Failed to create category: {e}")
        raise

def check_audit_logs(category_id=None):
    """Check audit logs in database."""
    print("\n" + "="*60)
    print("Checking audit logs in database...")
    print("="*60)
    
    # Wait a moment for async processing
    time.sleep(2)
    
    import subprocess
    
    # Check all catalog-inventory events
    result = subprocess.run([
        "docker", "exec", "soft-launch-postgres-1", 
        "psql", "-U", "postgres", "-d", "ntheemba",
        "-c", "SELECT event_type, payload->>'category_id' as cat_id, payload->>'business_id' as biz_id, created_at FROM audit_service.audit_logs WHERE service = 'catalog-inventory' ORDER BY created_at DESC LIMIT 5;"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    
    if category_id:
        # Check for specific category
        result = subprocess.run([
            "docker", "exec", "soft-launch-postgres-1",
            "psql", "-U", "postgres", "-d", "ntheemba",
            "-c", f"SELECT COUNT(*) FROM audit_service.audit_logs WHERE service = 'catalog-inventory' AND event_type = 'category_created' AND payload->>'category_id' = '{category_id}';"
        ], capture_output=True, text=True)
        print(f"\nEvents for category {category_id}:")
        print(result.stdout)

if __name__ == "__main__":
    try:
        category_id = test_category_creation()
        check_audit_logs(category_id)
        print("\n✅ Audit event emission test complete!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
