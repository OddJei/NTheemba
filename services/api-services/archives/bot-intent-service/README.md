# Bot Intent Service

Async FastAPI service that consumes enriched payloads, assembles context attachments for Gemini, and publishes intent results.

## Quick E2E (Redis Streams)

### 1) Start the service worker

Set `INTENT_WORKER_ENABLED=True` and run the FastAPI app (however you run services in this repo).

### 2) Publish a sample request

```powershell
Set-Location "c:\Users\SMART PC\Documents\NTheemba\services\bot services\bot-intent-service"
$env:REDIS_URL = "redis://localhost:6379/0"
python .\scripts\publish_intent_request.py
```

### 3) Tail results

```powershell
Set-Location "c:\Users\SMART PC\Documents\NTheemba\services\bot services\bot-intent-service"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:STREAM = "intent:results"
python .\scripts\tail_stream.py
```

### 4) Tail DLQ

```powershell
Set-Location "c:\Users\SMART PC\Documents\NTheemba\services\bot services\bot-intent-service"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:STREAM = "intent:dlq"
python .\scripts\tail_stream.py
```
