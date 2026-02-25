"""Collect run artifacts into a single overwriteable JSON file.

Usage:
  .\.venv\Scripts\python.exe src\scripts\collect_run_outputs.py

This script will look for JSON files under `src/scripts` matching
`*output.json` (including `seed_output.json` and `third_group_output.json`) and
merge them into `src/scripts/run_output.json`. It will also include the tail
of `uvicorn.err.log` and `uvicorn.out.log` (if present) to help debugging.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
import datetime
import os

SCRIPTS_DIR = Path(__file__).resolve().parent
OUT_FILE = SCRIPTS_DIR / "run_output.json"
LOG_CANDIDATES = [SCRIPTS_DIR.parent / "uvicorn.err.log", SCRIPTS_DIR / "uvicorn.err.log", SCRIPTS_DIR.parent / "uvicorn.out.log", SCRIPTS_DIR / "uvicorn.out.log"]


def _safe_load_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": f"failed to read json: {e}", "path": str(p)}


def _tail_file(p: Path, lines: int = 200) -> str:
    try:
        with p.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            size = 1024
            data = b""
            while end > 0 and data.count(b"\n") <= lines:
                start = max(0, end - size)
                fh.seek(start)
                chunk = fh.read(end - start)
                data = chunk + data
                end = start
                size *= 2
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = str(data)
            # return only last `lines` lines
            parts = text.splitlines()
            return "\n".join(parts[-lines:])
    except Exception as e:
        return f"<failed to tail {p}: {e}>"


def main():
    out: Dict[str, Any] = {
        "collected_at": datetime.datetime.utcnow().isoformat() + "Z",
        "artifacts": {},
        "logs": {},
    }

    # Collect JSON artifacts
    for p in sorted(SCRIPTS_DIR.glob("*_output.json")):
        key = p.name
        out["artifacts"][key] = {
            "path": str(p),
            "mtime": p.stat().st_mtime,
            "data": _safe_load_json(p),
        }

    # Also include seed_output.json if present (covers older naming)
    seed = SCRIPTS_DIR / "seed_output.json"
    if seed.exists():
        out["artifacts"][seed.name] = {
            "path": str(seed),
            "mtime": seed.stat().st_mtime,
            "data": _safe_load_json(seed),
        }

    # Tail logs if available
    for cand in LOG_CANDIDATES:
        if cand.exists():
            key = cand.name
            out["logs"][key] = {
                "path": str(cand),
                "tail": _tail_file(cand, lines=500),
                "size": cand.stat().st_size,
                "mtime": cand.stat().st_mtime,
            }

    # Write atomically
    tmp = OUT_FILE.with_suffix(OUT_FILE.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
        tmp.replace(OUT_FILE)
        print(f"Wrote {OUT_FILE}")
    except Exception as e:
        print(f"Failed to write {OUT_FILE}: {e}")


if __name__ == "__main__":
    main()
