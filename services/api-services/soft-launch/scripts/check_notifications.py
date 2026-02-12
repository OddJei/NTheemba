import json
import os
from collections import Counter

# Check notification storage
storage_path = 'services/notification/dev_notifications.json'

print('=' * 70)
print('NOTIFICATION STORAGE CHECK')
print('=' * 70)

if os.path.exists(storage_path):
    with open(storage_path) as f:
        data = json.load(f)
    
    notifs = data.get('notifications', [])
    print(f'Total notifications: {len(notifs)}')
    
    # Count by status
    statuses = Counter(n['status'] for n in notifs)
    print(f'\nStatus breakdown:')
    for status, count in statuses.items():
        print(f'  {status}: {count}')
    
    # Count by channel
    channels = Counter(n['channel'] for n in notifs)
    print(f'\nChannel breakdown:')
    for channel, count in channels.items():
        print(f'  {channel}: {count}')
    
    # Show recent
    recent = sorted(notifs, key=lambda x: x.get('created_at', ''), reverse=True)[:10]
    print(f'\nRecent 10 notifications:')
    for n in recent:
        print(f'  ID: {n["id"][:24]}... | Channel: {n["channel"]} | Status: {n["status"]}')
        print(f'      Created: {n["created_at"]}')
        if n.get('sent_at'):
            print(f'      Sent: {n["sent_at"]}')
        if n.get('error_message'):
            print(f'      Error: {n["error_message"]}')
        print()
else:
    print(f'❌ Storage not found at: {storage_path}')
    print('\nTrying alternate paths...')
    alt_paths = [
        './dev_notifications.json',
        '../notification/dev_notifications.json',
        'c:/Users/SMART PC/Documents/NTheemba/services/api-services/soft-launch/services/notification/dev_notifications.json'
    ]
    for alt in alt_paths:
        if os.path.exists(alt):
            print(f'✓ Found at: {alt}')
            break
    else:
        print('❌ Not found in any location')
