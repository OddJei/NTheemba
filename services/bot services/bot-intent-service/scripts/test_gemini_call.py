#!/usr/bin/env python3
__test__ = False  # prevent pytest from collecting/executing this script

import os
import sys
import json
import httpx
from pathlib import Path

# Load .env if present (simple loader, avoids extra deps)
def load_dotenv(path: str = ".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        # preserve already-set env vars
        os.environ.setdefault(k, v)


def main() -> int:
    load_dotenv()

    api_keys = os.getenv("INTENT_GEMINI_API_KEY") or os.getenv("gemini_key")
    if not api_keys:
        print("No INTENT_GEMINI_API_KEY found in environment or .env")
        return 2

    keys = [k.strip() for k in api_keys.split(",") if k.strip()]
    model = os.getenv("INTENT_GEMINI_MODEL", "gemini-3-flash-preview")
    endpoint = os.getenv("INTENT_GEMINI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/models")

    # Message to send
    user_text = os.getenv("RAW_TEXT", "hello")

    def model_resource(model_name: str) -> str:
        # Return the model id portion to append to the endpoint.
        # If user provided 'models/<id>' strip the prefix because the endpoint
        # already contains '/models'. This avoids constructing
        # '/models/models/<id>' which returns 404.
        if model_name.startswith("models/"):
            return model_name[len("models/"):]
        return model_name

    def call_with_key(key: str) -> int:
        model_id = model_resource(model)
        url = f"{endpoint}/{model_id}:generateContent"
        body = {"contents": [{"parts": [{"text": user_text}]}]}
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error for key: {e}")
            try:
                print(e.response.text)
            except Exception:
                pass
            return 1
        except Exception as e:
            print(f"Error calling Gemini: {e}")
            return 1

        print(json.dumps(data, indent=2, ensure_ascii=False)[:8000])
        candidates = data.get("candidates") or []
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts") or []
            if parts:
                text = parts[0].get("text", "")
                print("\n--- Model text output ---\n")
                print(text)
        return 0

    for i, k in enumerate(keys, start=1):
        print(f"Trying key {i}/{len(keys)}")
        code = call_with_key(k)
        if code == 0:
            return 0

    print("All keys failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
