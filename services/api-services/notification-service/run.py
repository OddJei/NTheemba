"""Run helper: start uvicorn using values from app.config.settings.

Usage examples:
  # normal (audit logging enabled)
  python run.py

  # disable audit posting (logs stay local)
  python run.py --no-audit-log

This script sets the AUDIT_ENABLED env var early so the application's
settings pick it up before modules are imported.
"""
import os
import sys

# Parse command-line flags that must affect settings BEFORE importing the app.
no_audit = False
no_notifier = False
args = []
for a in sys.argv[1:]:
  if a in ("--no-audit-log", "--no-audit", "--no-auditlog"):
    no_audit = True
  elif a in ("--no-notifier", "--no-notify", "--no-notifier-log"):
    no_notifier = True
  else:
    args.append(a)

if no_audit:
  # set env var so settings.AUDIT_ENABLED will be False
  os.environ.setdefault("AUDIT_ENABLED", "0")
if no_notifier:
  # set env var so settings.NOTIFIER_ENABLED will be False
  os.environ.setdefault("NOTIFIER_ENABLED", "0")

# Now import settings (which may read AUDIT_ENABLED)
from app.config.settings import settings

def _cli_get_port() -> int:
  # allow override via --port or PORT env var
  for i, a in enumerate(sys.argv[1:]):
    if a in ("--port", "-p") and i + 2 <= len(sys.argv[1:]):
      try:
        return int(sys.argv[i + 2])
      except Exception:
        pass
  return int(os.getenv("PORT", str(settings.SERVICE_PORT)))

if __name__ == "__main__":
  import uvicorn

  host = os.getenv("HOST", "127.0.0.1")
  port = _cli_get_port()

  # Use reload only in development (when running interactively).
  use_reload = os.getenv("UVICORN_RELOAD", "1") in ("1", "true", "True")

  uvicorn.run("app.main:app", host=host, port=port, reload=use_reload)
