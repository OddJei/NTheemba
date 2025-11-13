import os
import sys

# Ensure the service root (one level up from tests/) is on sys.path so tests can
# import the `app` package (e.g. `from app.ingress import enricher`).
SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SERVICE_ROOT not in sys.path:
    sys.path.insert(0, SERVICE_ROOT)
