#!/usr/bin/env python3
"""Run bot-session flow using msme access token and record responses."""
import json
from pathlib import Path

TOKEN_FILE = Path("scripts/msme_service_token.json")
OUT_DIR = Path("scripts")
BASE = "http://127.0.0.1:8540"

if not TOKEN_FILE.exists():
    print("token file missing", TOKEN_FILE)
    raise SystemExit(2)

token = json.loads(TOKEN_FILE.read_text())['access_token']
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

import requests

results = {}

# create bot
bot_payload = {"phone_number": "+260971111000", "type": "custom", "business_id": "c0dc894a-6ed5-4ba2-a276-54a864791bfb"}
r = requests.post(BASE + "/bot/create", json=bot_payload, headers=headers, timeout=10)
results['bot_create'] = {"status": r.status_code, "body": None}
try:
    results['bot_create']['body'] = r.json()
except Exception:
    results['bot_create']['body'] = r.text

# create session
session_payload = {"bot_phone": "+260971111000", "user_phone": "+260971111001", "platform": "whatsapp", "business_id": "c0dc894a-6ed5-4ba2-a276-54a864791bfb"}
r2 = requests.post(BASE + "/session/create", json=session_payload, headers=headers, timeout=10)
results['session_create'] = {"status": r2.status_code, "body": None}
try:
    results['session_create']['body'] = r2.json()
except Exception:
    results['session_create']['body'] = r2.text

session_id = None
if isinstance(results['session_create']['body'], dict):
    session_id = results['session_create']['body'].get('session_id')

# create event
if session_id:
    event_payload = {"session_id": session_id, "event_type": "enter_cart", "user_phone": "+260971111001"}
    r3 = requests.post(BASE + "/event/create", json=event_payload, headers=headers, timeout=10)
    results['event_create'] = {"status": r3.status_code, "body": None}
    try:
        results['event_create']['body'] = r3.json()
    except Exception:
        results['event_create']['body'] = r3.text

# write output
OUT_DIR.mkdir(parents=True, exist_ok=True)
Path(OUT_DIR / 'bot_flow_results.json').write_text(json.dumps(results, indent=2))
print('WROTE', OUT_DIR / 'bot_flow_results.json')
print('RESULTS SUMMARY:')
for k,v in results.items():
    print(k, v['status'])
