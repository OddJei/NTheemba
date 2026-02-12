"""
Simple test for media endpoints - tests endpoint logic without Nextcloud dependency
"""

import requests
from PIL import Image
import io
import subprocess
import json
import sys

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

CATALOG_URL = "http://localhost:8520"

def create_test_image(color, size=(100, 100)):
    """Create a test image with specific color."""
    img = Image.new('RGB', size, color=color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def get_product():
    """Get existing product from database."""
    output = subprocess.check_output([
        "docker", "exec", "soft-launch-postgres-1",
        "psql", "-U", "postgres", "-d", "ntheemba", "-t", "-c",
        "SELECT id FROM catalog_inventory.products LIMIT 1;"
    ], text=True)
    return output.strip()

def test_upload():
    """Test multiple file upload."""
    product_id = get_product()
    print(f"\n🧪 TEST: Upload Multiple Media Files")
    print(f"   Product ID: {product_id}")
    
    # Create test images
    files = [
        ('files', ('red.png', create_test_image('red'), 'image/png')),
        ('files', ('green.png', create_test_image('green'), 'image/png')),
        ('files', ('blue.png', create_test_image('blue'), 'image/png'))
    ]
    
    # Upload with green (index 1) as default
    response = requests.post(
        f"{CATALOG_URL}/catalog/product/{product_id}/media",
        files=files,
        data={'set_default_index': 1}
    )
    
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ Uploaded {result['total']} files")
        for media in result['uploaded']:
            default = "⭐" if media['is_default'] else "  "
            print(f"      {default} {media['filename']}")
    else:
        print(f"   ❌ Error: {response.text[:200]}")
    
    return product_id, response.status_code == 200

def test_set_default(product_id):
    """Test changing default media."""
    print(f"\n🧪 TEST: Set Default Media")
    
    response = requests.patch(
        f"{CATALOG_URL}/catalog/product/{product_id}/media/blue.png/set-default"
    )
    
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Changed default to blue.png")
    else:
        print(f"   ❌ Error: {response.text[:200]}")
    
    return response.status_code == 200

def test_delete(product_id):
    """Test deleting media."""
    print(f"\n🧪 TEST: Delete Media File")
    
    response = requests.delete(
        f"{CATALOG_URL}/catalog/product/{product_id}/media/red.png"
    )
    
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Deleted red.png")
    else:
        print(f"   ❌ Error: {response.text[:200]}")
    
    return response.status_code == 200

def verify_database(product_id):
    """Check database state."""
    print(f"\n📊 DATABASE VERIFICATION")
    
    output = subprocess.check_output([
        "docker", "exec", "soft-launch-postgres-1",
        "psql", "-U", "postgres", "-d", "ntheemba", "-t", "-c",
        f"SELECT media_urls FROM catalog_inventory.products WHERE id = '{product_id}';"
    ], text=True)
    
    if output.strip():
        media_urls = json.loads(output.strip())
        print(f"   Media files ({len(media_urls)}):")
        for media in media_urls:
            default = "⭐" if media.get('is_default') else "  "
            print(f"      {default} {media.get('filename')}")
        
        default_count = sum(1 for m in media_urls if m.get('is_default'))
        if default_count == 1:
            print(f"   ✅ Exactly one default file")
        else:
            print(f"   ⚠️  {default_count} default files (should be 1)")

if __name__ == "__main__":
    print("="*60)
    print("MEDIA ENDPOINTS TEST")
    print("="*60)
    
    try:
        product_id, success = test_upload()
        if success:
            verify_database(product_id)
            test_set_default(product_id)
            verify_database(product_id)
            test_delete(product_id)
            verify_database(product_id)
            
            print("\n" + "="*60)
            print("✅ ALL TESTS COMPLETED")
            print("="*60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
