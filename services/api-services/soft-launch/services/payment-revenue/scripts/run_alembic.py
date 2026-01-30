import os
import sys
from alembic.config import Config
from alembic import command

DB_URL = (
    "postgresql+asyncpg://postgres:!ladybug!%23!@127.0.0.1:5432/ntheemba?options=-csearch_path=payment_revenue"
)

def main():
    os.environ["DATABASE_URL"] = DB_URL
    here = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(here, ".."))
    os.chdir(repo_root)

    cfg = Config(os.path.join(repo_root, "alembic.ini"))
    # ensure env.py picks up our DATABASE_URL
    cfg.set_main_option("script_location", "alembic")

    try:
        command.upgrade(cfg, "head")
    except Exception as e:
        print("Migration failed:", e)
        sys.exit(2)

    print("Migration complete")


if __name__ == "__main__":
    main()
