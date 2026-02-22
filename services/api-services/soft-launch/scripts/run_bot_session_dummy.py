#!/usr/bin/env python3
import json
import requests
from pathlib import Path

BASE = "http://127.0.0.1:8540"
headers = {"Authorization": "Bearer dummy-token", "X-Business-Id": "c0dc894a-6ed5-4ba2-a276-54a864791bfb", "X-Role": "msme", "Content-Type": "application/json"}
out = {}

r = requests.post(BASE + "/bot/create", json={"phone_number": "+260971222000", "type": "custom", "business_id": "c0dc894a-6ed5-4ba2-a276-54a864791bfb"}, headers=headers, timeout=10)
out['bot_create'] = {'status': r.status_code, 'body': r.text}

r2 = requests.post(BASE + "/session/create", json={"bot_phone": "+260971222000", "user_phone": "+260971222001", "platform": "whatsapp", "business_id":"c0dc894a-6ed5-4ba2-a276-54a864791bfb"}, headers=headers, timeout=10)
out['session_create'] = {'status': r2.status_code, 'body': r2.text}

# save
Path('scripts').mkdir(parents=True, exist_ok=True)
Path('scripts/bot_dummy_results.json').write_text(json.dumps(out, indent=2))
print('WROTE scripts/bot_dummy_results.json')
print('BOT_CREATE', out['bot_create']['status'])
print('SESSION_CREATE', out['session_create']['status'])
