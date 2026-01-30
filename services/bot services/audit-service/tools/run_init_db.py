import sys
from pathlib import Path

# Ensure project root is on sys.path so `core` package can be imported when running
# this helper directly.
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from core import database


if __name__ == '__main__':
    print('Running init_db() to create schema and tables (if missing)')
    database.init_db()
    print('Done')
