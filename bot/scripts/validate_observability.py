"""Run the dependency-free Ntheemba observability self-check."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from dataclasses import asdict
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ntheemba.observability.self_check import run_observability_self_check


def _json_default(value: Any) -> str:
    return str(value)


async def _main() -> int:
    result = await run_observability_self_check()
    print(json.dumps(asdict(result), default=_json_default, indent=2, sort_keys=True))
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
