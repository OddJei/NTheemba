"""
Simple MSMe endpoint automation test functions.
One function per endpoint; a CLI runner calls them sequentially.

Usage (PowerShell):
  Set-Location services/msme-engine
  .\\.venv\\Scripts\\python.exe src\\scripts\\msme_endpoint_automation.py --base-url http://127.0.0.1:8500 --internal-secret 641c7813-f647-4a7b-9432-3bf314a81708
"""
from typing import Optional
import os
import argparse
import textwrap
import subprocess
import sys

try:
    import requests
except Exception:
    print("requests is required. Install with: pip install requests")
    raise

DEFAULT_BASE = "http://127.0.0.1:8500"
DEFAULT_INTERNAL_SECRET = os.environ.get("OUTBOX_INTERNAL_SECRET", "641c7813-f647-4a7b-9432-3bf314a81708")

# runtime-configurable
TIMEOUT = 30
FULL_BODY = False


def _print_resp(resp: requests.Response, full_body: Optional[bool] = None) -> None:
    if full_body is None:
        full_body = FULL_BODY
    print(f"-> {resp.status_code} {resp.reason}")
    ct = resp.headers.get("content-type", "")
    print(f"   Content-Type: {ct}")
    text = resp.text or ""
    if full_body:
        print("   Body (full):")
        # print raw bytes safely
        try:
            print("   " + "\n   ".join(text.splitlines()))
        except Exception:
            print("   <could not decode body as text>")
    else:
        preview = textwrap.shorten(text, width=800, placeholder="...")
        print("   Body preview:")
        print("   " + "\n   ".join(preview.splitlines()[:20]))


def check_health(base_url: str = DEFAULT_BASE) -> requests.Response:
    """GET /health"""
    url = f"{base_url.rstrip('/')}/health"
    print(f"[health] GET {url}")
    resp = requests.get(url, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def check_metrics(base_url: str = DEFAULT_BASE) -> requests.Response:
    """GET /metrics"""
    url = f"{base_url.rstrip('/')}/metrics"
    print(f"[metrics] GET {url}")
    resp = requests.get(url, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def get_openapi(base_url: str = DEFAULT_BASE) -> requests.Response:
    """GET /openapi.json"""
    url = f"{base_url.rstrip('/')}/openapi.json"
    print(f"[openapi] GET {url}")
    resp = requests.get(url, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def get_debug_env(base_url: str = DEFAULT_BASE) -> requests.Response:
    """GET /_debug/env"""
    url = f"{base_url.rstrip('/')}/_debug/env"
    print(f"[_debug/env] GET {url}")
    resp = requests.get(url, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def get_outbox_pending(base_url: str = DEFAULT_BASE, internal_secret: Optional[str] = None) -> requests.Response:
    """GET /outbox/pending"""
    url = f"{base_url.rstrip('/')}/outbox/pending"
    print(f"[outbox/pending] GET {url}")
    # This endpoint requires the internal secret header.
    secret = internal_secret or DEFAULT_INTERNAL_SECRET
    resp = requests.get(url, headers={"X-Internal-Secret": secret}, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def get_internal_businesses(base_url: str = DEFAULT_BASE, internal_secret: Optional[str] = None) -> requests.Response:
    """GET /internal/businesses (requires X-Internal-Secret)"""
    secret = internal_secret or DEFAULT_INTERNAL_SECRET
    url = f"{base_url.rstrip('/')}/internal/businesses"
    print(f"[internal/businesses] GET {url} (X-Internal-Secret provided)")
    resp = requests.get(url, headers={"X-Internal-Secret": secret}, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def get_internal_affiliates(base_url: str = DEFAULT_BASE, internal_secret: Optional[str] = None) -> requests.Response:
    """GET /internal/affiliates (requires X-Internal-Secret)"""
    secret = internal_secret or DEFAULT_INTERNAL_SECRET
    url = f"{base_url.rstrip('/')}/internal/affiliates"
    print(f"[internal/affiliates] GET {url} (X-Internal-Secret provided)")
    resp = requests.get(url, headers={"X-Internal-Secret": secret}, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def list_routes(base_url: str = DEFAULT_BASE) -> requests.Response:
    """GET /routes"""
    url = f"{base_url.rstrip('/')}/routes"
    print(f"[routes] GET {url}")
    resp = requests.get(url, timeout=TIMEOUT)
    _print_resp(resp)
    return resp


def run_all(base_url: str, internal_secret: Optional[str] = None) -> None:
    print(f"Running MSMe endpoint checks against {base_url}")
    try:
        check_health(base_url)
    except Exception as e:
        print(f"health failed: {e}")
    try:
        check_metrics(base_url)
    except Exception as e:
        print(f"metrics failed: {e}")
    try:
        get_openapi(base_url)
    except Exception as e:
        print(f"openapi failed: {e}")
    try:
        get_debug_env(base_url)
    except Exception as e:
        print(f"_debug/env failed: {e}")
    try:
        get_outbox_pending(base_url, internal_secret)
    except Exception as e:
        print(f"outbox/pending failed: {e}")
    try:
        get_internal_businesses(base_url, internal_secret)
    except Exception as e:
        print(f"internal/businesses failed: {e}")
    try:
        get_internal_affiliates(base_url, internal_secret)
    except Exception as e:
        print(f"internal/affiliates failed: {e}")
    try:
        list_routes(base_url)
    except Exception as e:
        print(f"routes failed: {e}")


def run_seed(base_url: str, internal_secret: Optional[str] = None) -> None:
    """Run the seed script from `src.scripts.seed_dummy_data` if available.

    The `OUTBOX_INTERNAL_SECRET` env var is passed to the subprocess when
    `internal_secret` is provided so the seeder's internal endpoint calls
    authenticate successfully.
    """
    script_path = 'src/scripts/seed_dummy_data.py'
    out_file = 'src/scripts/seed_output.json'
    cmd = [sys.executable, script_path, '--base-url', base_url, '--out-file', out_file]
    try:
        print(f"Running seed subprocess: {' '.join(cmd)}")
        env = os.environ.copy()
        if internal_secret:
            env['OUTBOX_INTERNAL_SECRET'] = internal_secret
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        print('--- seed stdout ---')
        print(proc.stdout)
        print('--- seed stderr ---')
        print(proc.stderr)
        if proc.returncode != 0:
            print(f"Seed script exited with code {proc.returncode}")
    except FileNotFoundError:
        print(f"Seed script not found at: {script_path}")
    except subprocess.TimeoutExpired:
        print("Seed script timed out")
    except Exception as e:
        print(f"Error running seed script: {e}")


def run_third_group(base_url: str, seed_file: str = 'src/scripts/seed_output.json', out_file: str = 'src/scripts/third_group_output.json', internal_secret: Optional[str] = None) -> None:
    """Run the `exercise_third_group.py` script using the provided seed file.

    Pass the internal secret into the subprocess so internal endpoints authenticate.
    """
    script_path = 'src/scripts/exercise_third_group.py'
    cmd = [sys.executable, script_path, '--base-url', base_url, '--seed-file', seed_file, '--out-file', out_file]
    if internal_secret:
        cmd.extend(['--internal-secret', internal_secret])
    try:
        print(f"Running third-group subprocess: {' '.join(cmd)}")
        env = os.environ.copy()
        if internal_secret:
            env['OUTBOX_INTERNAL_SECRET'] = internal_secret
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
        print('--- third-group stdout ---')
        print(proc.stdout)
        print('--- third-group stderr ---')
        print(proc.stderr)
        if proc.returncode != 0:
            print(f"Third-group script exited with code {proc.returncode}")
    except FileNotFoundError:
        print(f"Third-group script not found at: {script_path}")
    except subprocess.TimeoutExpired:
        print("Third-group script timed out")
    except Exception as e:
        print(f"Error running third-group script: {e}")


def _parse_args():
    p = argparse.ArgumentParser(description="MSMe endpoint automation checks")
    p.add_argument("--base-url", default=DEFAULT_BASE, help="Base URL for the msme-engine service")
    p.add_argument("--internal-secret", default=os.environ.get("OUTBOX_INTERNAL_SECRET", DEFAULT_INTERNAL_SECRET), help="X-Internal-Secret value")
    p.add_argument("--seed", action="store_true", help="Run seed script before checks")
    p.add_argument("--run-third-group", action="store_true", help="Run third-group exercise script after checks (uses seed_output.json)")
    p.add_argument("--timeout", type=int, default=TIMEOUT, help="Request timeout seconds (default: 10)")
    p.add_argument("--full-body", action="store_true", help="Print full response bodies instead of shortened preview")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    # apply runtime overrides
    TIMEOUT = args.timeout
    FULL_BODY = bool(args.full_body)
    if args.seed:
        print('Running seed script before endpoint checks...')
        run_seed(args.base_url, args.internal_secret)
    run_all(args.base_url, args.internal_secret)
    if args.run_third_group:
        print('Running third-group exercise script...')
        run_third_group(args.base_url, seed_file='src/scripts/seed_output.json', out_file='src/scripts/third_group_output.json', internal_secret=args.internal_secret)
