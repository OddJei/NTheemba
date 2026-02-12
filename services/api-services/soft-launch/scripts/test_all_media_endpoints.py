"""
Comprehensive test for all media upload endpoints:
1. POST /catalog/product/{id}/media - Upload multiple files with default selection
2. DELETE /catalog/product/{id}/media/{filename} - Delete a media file
3. PATCH /catalog/product/{id}/media/{filename}/set-default - Change default media
"""

import requests
import io
from PIL import Image
import psycopg2
import json
import time

# Configuration
MSME_ENGINE_URL = "http://localhost:8500"
CATALOG_URL = "http://localhost:8520"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "ntheemba",
    "user": "postgres",
    "password": "postgres"
}

def create_test_image(color, size=(100, 100)):
    """Create a test image with specific color."""
    img = Image.new('RGB', size, color=color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def get_auth_token():
    """Skip auth for now - endpoints don't require it."""
    print("🔐 Skipping auth (endpoints don't require token)...")
    return "dummy_token"

def get_existing_product():
    """Get an existing product ID from database."""
    print("\n📦 Getting existing product...")
    
    result = None
    try:
        import subprocess
        output = subprocess.check_output([
            "docker", "exec", "soft-launch-postgres-1",
            "psql", "-U", "postgres", "-d", "ntheemba", "-t", "-c",
            "SELECT id, name, business_id FROM catalog_inventory.products LIMIT 1;"
        ], text=True)
        
        if output.strip():
            parts = output.strip().split('|')
            if len(parts) >= 3:
                product_id = parts[0].strip()
                name = parts[1].strip()
                business_id = parts[2].strip()
                print(f"✅ Found product: {name} (ID: {product_id})")
                return product_id, business_id
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("❌ No products found")
    return None, None

def test_multiple_file_upload(token, product_id):
    """Test uploading multiple media files with default selection."""
    print("\n" + "="*70)
    print("TEST 1: Upload Multiple Media Files with Default Selection")
    print("="*70)
    
    # Create 3 test images with different colors
    red_img = create_test_image('red')
    green_img = create_test_image('green')
    blue_img = create_test_image('blue')
    
    files = [
        ('files', ('red_image.png', red_img, 'image/png')),
        ('files', ('green_image.png', green_img, 'image/png')),
        ('files', ('blue_image.png', blue_img, 'image/png'))
    ]
    
    # Set green (index 1) as default
    data = {'set_default_index': 1}
    
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"📤 Uploading 3 images (red, green, blue) - setting green as default...")
    response = requests.post(
        f"{CATALOG_URL}/catalog/product/{product_id}/media",
        files=files,
        data=data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Upload successful!")
        print(f"   Total uploaded: {result['total']}")
        print("\n   Uploaded files:")
        for media in result['uploaded']:
            default_marker = "⭐ DEFAULT" if media['is_default'] else ""
            print(f"   - {media['filename']} {default_marker}")
            print(f"     URL: {media['url'][:50]}...")
        return True
    else:
        print(f"❌ Upload failed: {response.text}")
        return False

def test_change_default(token, product_id):
    """Test changing the default media file."""
    print("\n" + "="*70)
    print("TEST 2: Change Default Media File")
    print("="*70)
    
    headers = {'Authorization': f'Bearer {token}'}
    filename = 'blue_image.png'
    
    print(f"🔄 Setting '{filename}' as new default...")
    response = requests.patch(
        f"{CATALOG_URL}/catalog/product/{product_id}/media/{filename}/set-default",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Default changed successfully!")
        print(f"   New default: {result['filename']}")
        return True
    else:
        print(f"❌ Failed to change default: {response.text}")
        return False

def verify_database_state(product_id):
    """Verify media_urls in database."""
    print("\n" + "="*70)
    print("VERIFICATION: Database State")
    print("="*70)
    
    try:
        import subprocess
        output = subprocess.check_output([
            "docker", "exec", "soft-launch-postgres-1",
            "psql", "-U", "postgres", "-d", "ntheemba", "-t", "-c",
            f"SELECT media_urls FROM catalog_inventory.products WHERE id = '{product_id}';"
        ], text=True)
        
        if output.strip():
            import json
            media_urls = json.loads(output.strip())
            print(f"📊 Media URLs in database:")
            for idx, media in enumerate(media_urls, 1):
                default_marker = "⭐ DEFAULT" if media.get('is_default') else ""
                print(f"   {idx}. {media.get('filename')} {default_marker}")
            
            default_count = sum(1 for m in media_urls if m.get('is_default'))
            if default_count == 1:
                print(f"\n✅ Exactly one file marked as default")
            else:
                print(f"\n⚠️  Warning: {default_count} files marked as default (should be 1)")
            return True
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def test_delete_media(token, product_id):
    """Test deleting a media file."""
    print("\n" + "="*70)
    print("TEST 3: Delete Media File")
    print("="*70)
    
    headers = {'Authorization': f'Bearer {token}'}
    filename = 'red_image.png'
    
    print(f"🗑️  Deleting '{filename}'...")
    response = requests.delete(
        f"{CATALOG_URL}/catalog/product/{product_id}/media/{filename}",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Deleted successfully!")
        print(f"   Deleted file: {result['filename']}")
        return True
    else:
        print(f"❌ Delete failed: {response.text}")
        return False

def check_audit_logs(business_id):
    """Check audit logs for media operations."""
    print("\n" + "="*70)
    print("VERIFICATION: Audit Logs")
    print("="*70)
    
    try:
        import subprocess
        output = subprocess.check_output([
            "docker", "exec", "soft-launch-postgres-1",
            "psql", "-U", "postgres", "-d", "ntheemba", "-t", "-c",
            f"""SELECT event_type, payload->>'filename' 
                FROM audit_service.audit_logs 
                WHERE service = 'catalog-inventory' 
                AND event_type IN ('media_uploaded', 'media_deleted', 'media_default_set') 
                ORDER BY created_at DESC LIMIT 10;"""
        ], text=True)
        
        if output.strip():
            lines = [l.strip() for l in output.strip().split('\n') if l.strip()]
            print(f"📝 Recent media audit events:")
            for line in lines:
                parts = line.split('|')
                if len(parts) >= 2:
                    event_type = parts[0].strip()
                    filename = parts[1].strip()
                    print(f"   - {event_type}: {filename}")
            print(f"\n✅ Found {len(lines)} audit events")
            return True
    except Exception as e:
        print(f"⚠️  Error checking audit logs: {e}")
    
    return False

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🚀 COMPREHENSIVE MEDIA ENDPOINTS TEST")
    print("="*70)
    
    # Step 1: Get auth token
    token = get_auth_token()
    if not token:
        print("\n❌ Cannot proceed without auth token")
        return
    
    # Step 2: Get existing product
    product_id, business_id = get_existing_product()
    if not product_id:
        print("\n❌ Cannot proceed without product")
        return
    
    # Test 1: Upload multiple files
    upload_success = test_multiple_file_upload(token, product_id)
    if not upload_success:
        print("\n❌ Upload test failed, stopping tests")
        return
    
    # Verify database after upload
    time.sleep(1)
    verify_database_state(product_id)
    
    # Test 2: Change default
    test_change_default(token, product_id)
    
    # Verify database after changing default
    time.sleep(1)
    verify_database_state(product_id)
    
    # Test 3: Delete media
    test_delete_media(token, product_id)
    
    # Final verification
    time.sleep(1)
    verify_database_state(product_id)
    
    # Check audit logs
    check_audit_logs(business_id)
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED")
    print("="*70)

if __name__ == "__main__":
    main()
