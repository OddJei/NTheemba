E2E test harness

This folder contains a minimal end-to-end test harness for local development.

Prerequisites
- Redis server reachable at REDIS_URL (default redis://localhost:6379/0)
- Bot and API services running against the dev sqlite DB (default services/ntheemba_api/fixtures/dev.sqlite)
- Optional mock servers running at http://localhost:5101 (SMS/OTP) and http://localhost:5102 (payments)

Run a single scenario:

```powershell
python .\run_e2e.py --scenario happy_text
```

Run all quick scenarios (payment requires --business-id):

```powershell
python .\run_e2e.py --scenario all --business-id 1
```

The script publishes messages to the incoming Redis list and listens for replies on the outgoing list. It polls the sqlite DB for expected rows and reports PASS/FAIL for each scenario. Tests are idempotent and use a unique prefix for message IDs.
