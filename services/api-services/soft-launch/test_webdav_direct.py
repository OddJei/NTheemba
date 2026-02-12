#!/usr/bin/env python3
from webdav3.client import Client
import io
import tempfile
import os

# Create client with proper URL
client = Client({
    'webdav_hostname': 'http://nextcloud/remote.php/dav/files/admin/',
    'webdav_login': 'admin',
    'webdav_password': 'admin123',
    'disable_check': True
})

# Try approach 1: mkdir then upload_to
print("=" * 50)
print("Approach 1: mkdir + upload_to")
print("=" * 50)
test_path = 'test_approach1/'
try:
    if not client.check(test_path):
        client.mkdir(test_path)
        print(f'Created {test_path}')
    client.upload_to(io.BytesIO(b'approach1'), f'{test_path}file.txt')
    print('SUCCESS with approach 1')
except Exception as e:
    print(f'FAILED: {e}')

# Try approach 2: Upload directly without mkdir
print("\n" + "=" * 50)
print("Approach 2: Direct upload without mkdir")
print("=" * 50)
test_path2 = 'direct_upload_test/file.txt'
try:
    client.upload_to(io.BytesIO(b'direct'), test_path2)
    print('SUCCESS with direct upload')
except Exception as e:
    print(f'FAILED: {e}')

# Try approach 3: Use local temp file and upload_file
print("\n" + "=" * 50)
print("Approach 3: Local file upload")
print("=" * 50)
with tempfile.NamedTemporaryFile(delete=False) as f:
    f.write(b'local file content')
    temp_path = f.name

try:
    client.upload_file(temp_path, 'test_localfile/uploaded.txt')
    print('SUCCESS with local file upload')
except Exception as e:
    print(f'FAILED: {e}')
finally:
    os.unlink(temp_path)

