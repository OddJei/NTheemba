from alembic.config import Config
from alembic import command

# Explicit DB URL to avoid shell quoting issues; change if needed
DB_URL = 'postgresql+asyncpg://postgres:%21ladybug%21%23%21@127.0.0.1:5432/ntheemba'

cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', DB_URL.replace('postgresql+asyncpg', 'postgresql', 1))

print('Running alembic upgrade head with URL:', cfg.get_main_option('sqlalchemy.url'))
command.upgrade(cfg, 'head')
print('Alembic upgrade completed')
