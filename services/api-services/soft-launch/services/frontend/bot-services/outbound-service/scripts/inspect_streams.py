from __future__ import annotations

import json
import os
from typing import Any

import redis


def main():
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.Redis.from_url(url, decode_responses=True)

    streams = ["outbound:requests", "outbound:http", "outbound:dlq"]

    print(f"Using REDIS_URL={url}\n")

    for s in streams:
        try:
            print(f"--- {s} ---")
            print("len:", r.xlen(s))
            try:
                groups = r.xinfo_groups(s)
            except Exception:
                groups = []
            print("groups:", json.dumps(groups, indent=2))
            try:
                items = r.xrange(s, count=10)
                print("last items:")
                for i in items:
                    print(i)
            except Exception as e:
                print("read error:", e)
        except Exception as exc:
            print("error inspecting stream:", s, exc)


if __name__ == "__main__":
    main()
