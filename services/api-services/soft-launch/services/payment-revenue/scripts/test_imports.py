import sys
print('start')
try:
    from alembic.config import Config
    print('got Config')
except Exception as e:
    print('import error', repr(e))
    sys.exit(1)

try:
    from alembic import command
    print('got command')
except Exception as e:
    print('command import error', repr(e))
    sys.exit(2)

print('done imports')
