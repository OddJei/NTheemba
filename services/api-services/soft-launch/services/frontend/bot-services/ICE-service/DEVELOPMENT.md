# ICE Service - Local Development & Simulation

This guide shows how to run the ICE service locally while backend services run in Docker containers, and how to simulate bot session workflows.

## Architecture

```
LOCAL DEVELOPMENT SETUP:
┌─────────────────────────────────────────────┐
│  Local Machine (Windows PowerShell venv)    │
│  ┌────────────────────────────────────────┐ │
│  │  ICE Service (FastAPI + asyncio)       │ │
│  │  - app/adapters/bot_session.py         │ │
│  │  - app/adapters/user_bot_session.py    │ │
│  │  - app/adapters/auth.py                │ │
│  └────────────────────────────────────────┘ │
│  Calls: localhost:8000, :8500, :8530, etc   │
└─────────────────────────────────────────────┘
         │
         │ HTTP (localhost ports)
         │
┌────────▼─────────────────────────────────────┐
│ Docker Compose Network (softlaunch-net)      │
│                                              │
│  ┌──────────────┐  ┌──────────────┐        │
│  │ bot-session  │  │ msme-engine  │        │
│  │  :8000       │  │   :8500      │        │
│  └──────────────┘  └──────────────┘        │
│                                              │
│  ┌──────────────┐  ┌──────────────┐        │
│  │  postgres    │  │    redis     │        │
│  │  :5432       │  │   :6379      │        │
│  └──────────────┘  └──────────────┘        │
│                                              │
│  ┌──────────────────────────────────────┐  │
│  │ Other Backend Services               │  │
│  │ catalog, cart, payment, etc.         │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## Prerequisites

1. **Docker & Docker Compose** - Running backend services
2. **Python 3.10+** - For ICE service
3. **Virtual Environment** - Isolated Python env

## Setup Steps

### 1. Start Backend Services

```powershell
# Navigate to workspace root
cd c:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch

# Start services (docker-compose will expose ports on localhost)
docker-compose up -d bot-session msme-engine postgres redis

# Verify services are running
docker-compose ps
```

Expected output:
```
CONTAINER ID   IMAGE              STATUS          PORTS
xxx            bot-session        Up 2 minutes    8000/tcp
xxx            msme-engine        Up 2 minutes    8500/tcp
xxx            postgres           Up 2 minutes    5432/tcp
xxx            redis              Up 2 minutes    6379/tcp
```

### 2. Setup ICE Service Environment

```powershell
# Navigate to ICE service directory
cd services\frontend\bot-services\ICE-service

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Create .env file for local development
cp .env.local .env

# Verify configuration
cat .env
```

Your `.env.local` should have:
```
ENVIRONMENT=local
BOT_SESSION_URL=http://localhost:8000
MSME_ENGINE_URL=http://localhost:8500
REDIS_URL=redis://localhost:6379/0
```

### 3. Run the Simulation

```powershell
# From ICE-service directory with venv activated

# Run the simulation script
python -m scripts.simulate_session_workflow

# Or run as module
python scripts/simulate_session_workflow.py
```

Expected output:
```
======================================================================
ICE SERVICE SIMULATION: Bot Session & User-Bot Session Workflow
======================================================================
============================================================
ICE Service Configuration (ENVIRONMENT=local)
============================================================
  environment: local
  bot_session_url: http://localhost:8000
  msme_engine_url: http://localhost:8500
  ...
============================================================

[STEP 1] Health Checks
----------------------------------------------------------------------
Checking bot-session service...
  Bot-session health: True
Checking MSME Engine service...
  MSME Engine health: True

[STEP 2] Authenticate User
----------------------------------------------------------------------
Verifying user: 260701234567
  User verified:
    Role: registered
    Status: active
    Business ID: BIZ-001

[STEP 3] Create Bot Session
----------------------------------------------------------------------
Creating bot session structure...
  Bot-session infrastructure adapter is ready

[STEP 4] Create User-Bot Session
----------------------------------------------------------------------
Creating session for user: 260701234567
  Business ID: BIZ-TEST-001
  Platform: whatsapp
  Bot Phone: 260709999999
✓ Session created successfully!
  Session ID: sess-abc123def456
  Status: active
  State: chat
  Session Mode: public
  Created At: 2026-02-04T12:00:00Z

[STEP 5] Query Active Sessions
----------------------------------------------------------------------
Getting active sessions for: 260701234567
✓ Found 1 active sessions
  Session 1:
    ID: sess-abc123def456
    Status: active
    Mode: public

[STEP 6] Close User-Bot Session
----------------------------------------------------------------------
Closing session: sess-abc123def456
✓ Session closed successfully!
  Updated Status: closed

[STEP 7] Reactivate Session
----------------------------------------------------------------------
Reactivating session for: 260701234567
✓ Session reactivated!
  Session ID: sess-abc123def456
  Status: active
  Reactivated: true

[CLEANUP] Closing adapters...
✓ Cleanup complete

======================================================================
SIMULATION COMPLETED SUCCESSFULLY!
======================================================================
```

## Environment Configuration

### Local Development (.env.local)
```bash
ENVIRONMENT=local                              # ICE in venv, backends in Docker
BOT_SESSION_URL=http://localhost:8000          # Maps to Docker container port
MSME_ENGINE_URL=http://localhost:8500
# ... other services on localhost:PORT
```

### Docker Compose (.env.docker)
```bash
ENVIRONMENT=docker                             # ICE in container too
BOT_SESSION_URL=http://bot-session:8000        # Container network name
MSME_ENGINE_URL=http://msme-engine:8500
# ... other services on container names
```

## Testing

### Unit Tests (Mocked Services)

```powershell
# Run all unit tests
pytest app/adapters/tests/test_bot_session.py -v
pytest app/adapters/tests/test_user_bot_session.py -v

# Run with coverage
pytest app/adapters/tests/test_bot_session.py --cov=app/adapters
```

### Integration Tests (Real Services)

```powershell
# Run integration tests (requires services running)
pytest app/adapters/tests/test_integration_bot_session.py -v -s

# Run with verbose output
pytest app/adapters/tests/test_integration_bot_session.py::TestBotSessionIntegration::test_health_check_real_service -v -s
```

## Troubleshooting

### Bot-session service not running

```powershell
# Check if containers are running
docker-compose ps

# Start bot-session
docker-compose up -d bot-session

# Check logs
docker-compose logs bot-session
```

### Connection refused errors

```powershell
# Verify ports are accessible
curl http://localhost:8000/health          # Bot-session
curl http://localhost:8500/health          # MSME Engine

# On Windows (alternative)
(Invoke-WebRequest -Uri http://localhost:8000/health).Content
```

### Environment not loading

```powershell
# Verify .env file exists and has correct format
cat .env

# Check ENVIRONMENT variable is set
$env:ENVIRONMENT

# Force set environment
$env:ENVIRONMENT="local"
$env:BOT_SESSION_URL="http://localhost:8000"
```

## Adapters Reference

### BotSessionServiceAdapter
Low-level session storage and infrastructure operations

```python
from app.adapters.factory import AdapterFactory

adapter = AdapterFactory.get_bot_session_adapter()
await adapter.health_check()
session = await adapter.fetch_session("sess-123")
```

### UserBotConversationAdapter
User-bot conversation lifecycle management

```python
adapter = AdapterFactory.get_user_bot_session_adapter()
session = await adapter.create_session(
    "260701234567", 
    "BIZ-001",
    {"platform": "whatsapp"}
)
await adapter.close_session(session["session_id"], "test_complete")
```

### AuthenticationAdapter
User authentication via MSME Engine

```python
from app.adapters.auth import AuthenticationAdapter

auth = AuthenticationAdapter()
user_info = await auth.verify_user("260701234567")
business = await auth.get_business_profile("BIZ-001")
```

## Next Steps

1. **Implement remaining adapters** (catalog, cart, payment, delivery, affiliate, MSME)
2. **Add Phase 2: Persistence & Cache Layer** (Postgres, Redis)
3. **Implement Phase 3: Orchestration Layer** (hydrate, reserve, confirm workflows)
4. **Create Phase 4: Bot-Facing API** (FastAPI endpoints)

See [IMPLEMENTATION.md](./IMPLEMENTATION.md) for detailed roadmap.
