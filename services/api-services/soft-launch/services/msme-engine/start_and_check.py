import os
import subprocess
import time
import urllib.request
import urllib.error
import sys

cwd = os.path.abspath(os.path.dirname(__file__))
py = os.path.join(cwd, '.venv', 'Scripts', 'python.exe')
if not os.path.exists(py):
    # fallback to system python
    py = sys.executable

env = os.environ.copy()
env['DATABASE_URL'] = 'postgresql+asyncpg://postgres:!ladybug!#!@127.0.0.1:5432/ntheemba'
env['PG_SCHEMA'] = 'msme_engine'
env['OUTBOX_INTERNAL_SECRET'] = 'testsecret'

print('Using python:', py)
print('Starting uvicorn...')
p = subprocess.Popen([py, '-u', '-m', 'uvicorn', 'src.app.main:app', '--host', '127.0.0.1', '--port', '8500', '--log-level', 'info'], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(4)
# capture some uvicorn output for up to 6 seconds
start_time = time.time()
out_lines = []
while time.time() - start_time < 6:
    try:
        if p.stdout is not None:
            line = p.stdout.readline()
        else:
            line = ''
    except Exception:
        line = ''
    if line:
        out_lines.append(line)
    else:
        time.sleep(0.1)

# print captured uvicorn logs
if out_lines:
    print('--- uvicorn captured output ---')
    print(''.join(out_lines))

# try health
try:
    with urllib.request.urlopen('http://127.0.0.1:8500/health', timeout=5) as r:
        body = r.read().decode()
        print('HEALTH_OK:', body)
        status_ok = True
except Exception as e:
    print('HEALTH_ERR:', e)
    status_ok = False

# print any remaining uvicorn output
try:
    remaining = ''
    if p.stdout is not None:
        remaining = p.stdout.read()
    if remaining:
        print('--- uvicorn remaining output ---')
        print(remaining)
except Exception as e:
    print('failed to read uvicorn output:', e)

# terminate server
try:
    p.terminate()
    p.wait(timeout=3)
except Exception:
    try:
        p.kill()
    except Exception:
        pass

sys.exit(0 if status_ok else 1)
