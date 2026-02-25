import asyncio
import os
import sys
import json
import uuid
from pathlib import Path

# Ensure both 'src' and 'app' import styles resolve when running ad-hoc scripts
repo_root = Path(__file__).resolve().parents[2]
src_dir = repo_root / "src"
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(repo_root))

# debug helpers to diagnose import path issues
print('ENV PYTHONPATH=', os.environ.get('PYTHONPATH'))
print('CWD=', os.getcwd())
print('sys.path (head)=', sys.path[:6])

from src.app.db import SessionLocal

async def main():
    async with SessionLocal() as db:
        try:
            from src.app.helpers.notification_helpers import emit_notification_outbox
            out_id = await emit_notification_outbox(db, channel='in_app', user_id=None, business_id=str(uuid.uuid4()), payload={'test': 'hello'}, dedupe_key=None)
            print('WROTE OUTBOX ID:', out_id)
        except Exception as e:
            print('EMIT FAILED:', type(e), e)

if __name__ == '__main__':
    asyncio.run(main())
