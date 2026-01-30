#!/usr/bin/env python3
import os
from pathlib import Path
import httpx
import json
import sys

# load .env simple
p = Path('.env')
if p.exists():
    for line in p.read_text(encoding='utf8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

api_keys = os.getenv('INTENT_GEMINI_API_KEY') or os.getenv('gemini_key')
if not api_keys:
    print('No API keys found in environment or .env')
    sys.exit(2)

keys = [k.strip() for k in api_keys.split(',') if k.strip()]
endpoint = os.getenv('INTENT_GEMINI_ENDPOINT', 'https://generativelanguage.googleapis.com/v1beta/models')

print('Trying', len(keys), 'key(s) against', endpoint)

for i, key in enumerate(keys, start=1):
    print('\n--- Key', i, '---')
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(endpoint, params={'key': key})
            print('HTTP', resp.status_code)
            text = resp.text
            try:
                data = resp.json()
            except Exception:
                print('Response not JSON; raw:')
                print(text[:2000])
                continue

            # Print summary of returned models or error
            if resp.status_code == 200:
                # response may be {'models': [...]}
                models = data.get('models') or data.get('model') or data.get('availableModels') or None
                if models:
                    print('Found models:', len(models))
                    for m in models[:50]:
                        # try to print name/id
                        if isinstance(m, dict):
                            name = m.get('name') or m.get('model') or m.get('id') or str(m)
                            print(' -', name)
                        else:
                            print(' -', m)
                else:
                    # print keys in response
                    print('Response keys:', list(data.keys()))
                    print(json.dumps(data, indent=2)[:2000])
            else:
                print('Error response:')
                print(json.dumps(data, indent=2)[:2000])
    except httpx.HTTPStatusError as e:
        print('HTTP error:', e)
    except Exception as e:
        print('Error calling endpoint:', e)

print('\nDone')
