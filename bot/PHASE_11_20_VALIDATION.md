# Phase 11.20 Validation Record

Run from the project root:

```powershell
python -m pytest
python -m compileall ntheemba tests scripts
python scripts\validate_observability.py
python scripts\validate_phase_11_20.py
python -m ruff check .
python -m ruff format --check .
python -m mypy ntheemba tests
```

Validated in the packaging environment (final suite: 310 tests):

- complete automated test suite;
- Python compilation;
- observability self-check;
- Phase 11.20 synthetic acceptance script;
- manual Serah booking path;
- manual loyalty path;
- manual capability-denial path.

Ruff and MyPy require the development dependencies and must be run in the local project environment when those tools are installed.
