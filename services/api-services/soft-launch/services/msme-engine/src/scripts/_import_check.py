import sys
import importlib
from pathlib import Path

# Ensure project `src` is on sys.path when running from workspace root
proj_root = Path(__file__).resolve().parents[1]
src_path = proj_root / "src"
sys.path.insert(0, str(src_path))

importlib.import_module('src.app.helpers.outbox.outbox')
print('OK')
