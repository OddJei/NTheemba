import os
import sys
import json
import asyncio

# Load .env into environment
env_path = os.path.join(os.path.dirname(__file__), 'services', 'frontend', 'bot-services', 'custom-bot-service', '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

# Ensure app directory is on sys.path
# Add the parent package directory so `app` can be imported as a package
pkg_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), 'services', 'frontend', 'bot-services', 'custom-bot-service'))
if pkg_parent not in sys.path:
    sys.path.insert(0, pkg_parent)

# Import runtime as a package module (`app` package)
import importlib
engine = importlib.import_module('app.runtime_engine')

# Stub OOBStore and IceClient to avoid Redis/ICE dependencies
class DummyStore:
    async def create_default_if_missing(self, session_id):
        return ({'meta': {}}, 1)

    async def cas_update(self, session_id, updater):
        oob = {'meta': {}}
        updated = updater(oob)
        return (updated, 1)

    async def set_last_event(self, session_id, event_id):
        return True

class DummyIce:
    def __init__(self):
        self.enabled = False

engine.OOBStore = DummyStore
engine.IceClient = DummyIce

async def run_once():
    payload = {'meta': {'session': {'stage': 'cart'}}, 'text': 'I want to buy'}
    res = await engine.process_event(payload=payload, event_id='evt-integ-run', session_id='sess-integ-run')
    print(json.dumps(res, indent=2))

if __name__ == '__main__':
    asyncio.run(run_once())
