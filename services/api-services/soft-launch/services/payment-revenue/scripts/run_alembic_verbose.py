import os
import sys
from alembic.config import Config
from alembic import command

DB_URL = (
    "postgresql+asyncpg://postgres:!ladybug!%23!@127.0.0.1:5432/ntheemba?options=-csearch_path=payment_revenue"
)

def main():
    print('Using Python:', sys.executable)
    os.environ["DATABASE_URL"] = DB_URL
    print('DATABASE_URL set')
    here = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(here, ".."))
    os.chdir(repo_root)
    print('CWD ->', os.getcwd())

    cfg = Config(os.path.join(repo_root, "alembic.ini"))
    cfg.set_main_option("script_location", "alembic")

    try:
        print('Starting alembic upgrade head...')
        command.upgrade(cfg, "head")
        print('Alembic upgrade finished successfully')
    except Exception as e:
        print('Migration failed:', repr(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
