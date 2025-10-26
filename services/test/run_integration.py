#!/usr/bin/env python3
"""Simple integration test that runs the mock gateway and the persistence API,
posts a register request and verifies the mock gateway recorded an outbound call.

This script is intended to be run from the repo root and uses the API venv
located at services/ntheemab_api/.venv. It spawns subprocesses and then
performs HTTP checks against the running services.

Usage (PowerShell):
    cd C:/Users/SMART PC/Documents/NTheemba
    python services/test/run_integration.py

"""
from __future__ import annotations
import subprocess
import os
import sys
import time
import requests
import json
from pathlib import Path
import argparse

# redis optional imports
try:
    import redis
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False
from datetime import datetime


ROOT = Path(__file__).resolve().parents[2]
API_DIR = ROOT / "services" / "ntheemab_api"
# mock server has been moved to services/test/mock_server
MOCK_DIR = ROOT / "services" / "test" / "mock_server"
API_VENV_PY = API_DIR / ".venv" / "Scripts" / "python.exe"
if not API_VENV_PY.exists():
    # fallback to system python
    API_VENV_PY = sys.executable

MOCK_PORT = 5050
API_PORT = 8000
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
REDIS_QUEUE_IN = os.environ.get("REDIS_QUEUE_IN", "ntheemba:incoming")
REDIS_QUEUE_OUT = os.environ.get("REDIS_QUEUE_OUT", "ntheemba:outgoing")


def start_mock():
    # Prefer to run the mock server with the API venv python, but if that
    # interpreter doesn't have Flask installed fall back to the system
    # python (the one running this script). This avoids ModuleNotFoundError
    # when the API venv doesn't include dev-only deps like Flask.
    def python_has_module(python_exe: Path | str, module: str) -> bool:
        try:
            res = subprocess.run([str(python_exe), "-c", f"import {module}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode == 0
        except Exception:
            return False

    mock_python = API_VENV_PY
    if not python_has_module(mock_python, "flask"):
        # fall back to the interpreter running this script
        mock_python = sys.executable

    cmd = [str(mock_python), "app.py"]
    proc = subprocess.Popen(cmd, cwd=str(MOCK_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc


def start_api():
    # Start the API with uvicorn using the API venv python and point GATEWAY_BASE_URL to mock
    app_module = "ntheemba.persistence.main:app"
    cmd = [str(API_VENV_PY), "-m", "uvicorn", app_module, "--host", "127.0.0.1", "--port", str(API_PORT)]
    env = os.environ.copy()
    env["GATEWAY_BASE_URL"] = f"http://127.0.0.1:{MOCK_PORT}"
    env["DATABASE_URL"] = f"sqlite:///{str(API_DIR / 'fixtures' / 'dev.sqlite')}"
    proc = subprocess.Popen(cmd, cwd=str(API_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    return proc


def wait_for(url: str, timeout: int = 10) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def find_mock_event(kind: str = "/notify") -> dict | None:
    # look into mock_server/logs for recent events and find an endpoint match
    log_dir = MOCK_DIR / "logs"
    if not log_dir.exists():
        return None
    files = sorted(log_dir.glob("events-*.jsonl"), reverse=True)
    for f in files:
        try:
            with f.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                        if rec.get("endpoint", "").startswith(kind):
                            return rec
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--enqueue-inbound", action="store_true", help="After posting to API also enqueue an inbound message to the bot Redis queue")
    parser.add_argument("--check-outgoing", action="store_true", help="If enqueueing, also wait for an outgoing message on the outgoing queue")
    parser.add_argument("--out-wait", type=int, default=10, help="Seconds to wait for outgoing reply when --check-outgoing is used")
    args = parser.parse_args()

    print("Starting integration test: mock -> api -> verify")
    mock_proc = start_mock()
    try:
        print("Waiting for mock server to be ready...")
        if not wait_for(f"http://127.0.0.1:{MOCK_PORT}/health", timeout=10):
            print("Mock server did not become ready in time")
            stderr = getattr(mock_proc, "stderr", None)
            if stderr is not None:
                try:
                    print(stderr.read())
                except Exception:
                    pass
            mock_proc.kill()
            sys.exit(2)

        api_proc = start_api()
        try:
            print("Waiting for API to be ready...")
            if not wait_for(f"http://127.0.0.1:{API_PORT}/health", timeout=15):
                print("API did not become ready in time")
                # dump stderr
                out, err = api_proc.communicate(timeout=1)
                print("API stdout:", out)
                print("API stderr:", err)
                api_proc.kill()
                mock_proc.kill()
                sys.exit(2)

            # perform register request
            payload = {
                "phone": "260977009900",
                "name": "Integration Test MSME",
                "email": "it@example.com",
                "accepted_tos": True,
                "meta": {"role": "msme_owner", "test_id": "int-test-1"},
                "business": {"business_id": "it_msme_1", "name": "IT MSME", "owner_phone": "260977009900", "meta": {"address": "Test St"}},
            }

            print("Posting register payload to API...", payload)
            r = requests.post(f"http://127.0.0.1:{API_PORT}/profile/register", json=payload, timeout=10)
            print("API response:", r.status_code, r.text)
            if r.status_code not in (200, 201):
                print("Register failed")
                raise SystemExit(3)

            # Enqueue an inbound message to Redis so the bot's incoming queue worker
            # can pick up the registration flow (if the bot and Redis are running).
            def enqueue_to_redis_message(from_phone: str, request_id: str, message: str, queue_key: str = "ntheemba:incoming") -> bool:
                try:
                    import redis as _redis
                except Exception:
                    print("redis package not available in this Python environment. Skipping enqueue. Install with: pip install redis")
                    return False
                redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
                try:
                    client = _redis.from_url(redis_url)
                    msg = {
                        "to": "ntheemba",
                        "from": from_phone,
                        "request_id": request_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "message": message,
                        "meta": {"test_id": payload.get("meta", {}).get("test_id")}
                    }
                    client.rpush(queue_key, json.dumps(msg))
                    print(f"Enqueued message to Redis key {queue_key} ->", msg)
                    return True
                except Exception as e:
                    print("Failed to enqueue to Redis:", str(e))
                    return False

            # Attempt to enqueue a trigger message for the bot
            enqueue_to_redis_message(from_phone=payload["phone"], request_id=payload["meta"].get("test_id", "int-test-1"), message="Start registration")

            # wait a short while for API to call mock
            print("Waiting for mock to record notify/payment call...")
            found = None
            deadline = time.time() + 10
            while time.time() < deadline and found is None:
                # check for notify or payment prompt
                found = find_mock_event("/notify") or find_mock_event("/payment/prompt")
                if found:
                    break
                time.sleep(0.5)

            if not found:
                print("No notify/payment event found in mock logs")
                # print recent mock stderr/stdout
                try:
                    stdout = getattr(mock_proc, "stdout", None)
                    stderr = getattr(mock_proc, "stderr", None)
                    if stdout is not None:
                        out = stdout.read()
                        print("Mock stdout:", out)
                    if stderr is not None:
                        err = stderr.read()
                        print("Mock stderr:", err)
                except Exception:
                    pass
                raise SystemExit(4)

            # optional: enqueue an inbound message into Redis so the bot's queue worker can pick it up
            if args.enqueue_inbound:
                if not REDIS_AVAILABLE:
                    print("Redis support is not available in this Python interpreter (redis package missing). Install 'redis' package to enable enqueueing.")
                    raise SystemExit(5)

                # Build a simple inbound message the bot expects
                inbound = {
                    "to": "ntheemba",
                    "from": payload["phone"],
                    "request_id": payload.get("meta", {}).get("test_id", "int-test-1"),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "message": "START REGISTRATION",
                    "meta": payload.get("meta", {}),
                }

                try:
                    print(f"Enqueueing inbound message to Redis {REDIS_URL} -> {REDIS_QUEUE_IN}:", inbound)
                    rconn = redis.from_url(REDIS_URL)
                    rconn.rpush(REDIS_QUEUE_IN, json.dumps(inbound))
                    print("Enqueued inbound message.")
                except Exception as e:
                    print("Failed to enqueue inbound message:", e)
                    raise SystemExit(6)

                # optionally wait for outgoing reply
                if args.check_outgoing:
                    try:
                        print(f"Waiting up to {args.out_wait}s for a message on outgoing queue '{REDIS_QUEUE_OUT}'...")
                        # BLPOP returns (queue_name, value) or None
                        r = rconn.blpop(REDIS_QUEUE_OUT, timeout=args.out_wait)
                        if r is None:
                            print("No outgoing message received within timeout.")
                            raise SystemExit(7)
                        else:
                            qname, val = r
                            try:
                                parsed = json.loads(val)
                            except Exception:
                                parsed = val
                            print("Received outgoing message:", parsed)
                    except Exception as e:
                        print("Error while waiting for outgoing message:", e)
                        raise SystemExit(8)

            print("Found mock event:")
            print(json.dumps(found, indent=2))
            print("Integration test PASSED")

        finally:
            print("Shutting down API...")
            api_proc.terminate()
            try:
                api_proc.wait(timeout=3)
            except Exception:
                api_proc.kill()
    finally:
        print("Shutting down mock server...")
        mock_proc.terminate()
        try:
            mock_proc.wait(timeout=3)
        except Exception:
            mock_proc.kill()


if __name__ == "__main__":
    main()
