import time
from core.database import SessionLocal

def run_retention(retention_days: int = 90):
    """Placeholder retention job: mark or move records older than retention_days"""
    db = SessionLocal()
    try:
        # Implement archival logic here: move to object storage and mark archived=True
        print(f"Running retention job: retention_days={retention_days}")
    finally:
        db.close()

if __name__ == '__main__':
    # simple runner for manual testing
    run_retention()
