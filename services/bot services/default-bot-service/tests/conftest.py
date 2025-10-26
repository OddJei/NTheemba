import sys
from pathlib import Path


def pytest_configure():
    # Ensure the default-bot-service package root is on sys.path so imports like
    # `models.node` and `utils.payload_validator` resolve during test collection.
    tests_dir = Path(__file__).resolve().parent
    project_root = tests_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
