# ICE Service: Local Development Setup Complete ✅

## What Was Implemented

### 1. **Smart Configuration System** (`app/config.py`)
- ✅ Automatic environment detection (local vs Docker)
- ✅ Dynamic default URLs based on `ENVIRONMENT` variable
- ✅ Local development: `BOT_SESSION_URL=http://localhost:8000`
- ✅ Docker deployment: `BOT_SESSION_URL=http://bot-session:8000`

### 2. **Authentication Adapter** (`app/adapters/auth.py`)
- ✅ Shared auth adapter for MSME Engine calls
- ✅ User verification: `verify_user(phone_number)` → Gets role, business_id, status
- ✅ Business profile retrieval: `get_business_profile(business_id)`
- ✅ Used for session context enrichment

### 3. **Session Workflow Simulation** (`scripts/simulate_session_workflow.py`)
A complete demonstration script showing:
- ✅ Health checks (bot-session, MSME Engine)
- ✅ User authentication
- ✅ Bot session creation
- ✅ User-bot session creation
- ✅ Session state queries
- ✅ Session closure
- ✅ Session reactivation

### 4. **Environment Files**
- ✅ `.env.local` - Local development (ICE in venv, backends in Docker)
- ✅ `.env.docker` - Docker Compose (all services in containers)
- ✅ `.env.example` - Reference template

### 5. **Development Guide** (`DEVELOPMENT.md`)
Complete documentation including:
- ✅ Architecture diagram (local vs Docker)
- ✅ Setup steps
- ✅ How to run simulation
- ✅ Testing instructions
- ✅ Troubleshooting guide

---

## How to Use

### **Quick Start (5 minutes)**

```powershell
# 1. Start Docker containers
cd c:\Users\SMART PC\Documents\NTheemba\services\api-services\soft-launch
docker-compose up -d bot-session msme-engine postgres redis

# 2. Setup ICE service
cd services\frontend\bot-services\ICE-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Copy local environment
cp .env.local .env

# 4. Run simulation
python -m scripts.simulate_session_workflow
```

### **What Happens**

The simulation demonstrates:

1. **Health Checks** - Verifies bot-session and MSME Engine are running
2. **User Authentication** - Fetches user role and business info from MSME Engine
3. **Session Lifecycle**:
   - Create user-bot session
   - Query active sessions
   - Close session
   - Reactivate session

---

## Architecture: Local Development

```
┌─────────────────────────────────────┐
│ Local PC (PowerShell venv)          │
│ ICE Service                         │
│ - Adapters                          │
│ - Auth                              │
│ - Config (ENVIRONMENT=local)        │
└────────────┬────────────────────────┘
             │ HTTP to localhost:PORT
             │
┌────────────▼────────────────────────┐
│ Docker Containers                   │
│ (softlaunch-net network)            │
│                                     │
│ bot-session:8000                   │
│ msme-engine:8500                   │
│ postgres:5432                      │
│ redis:6379                         │
│ ... other backends                 │
└─────────────────────────────────────┘
```

**ICE service** runs in your local venv and makes HTTP calls to `localhost:PORT`
**Docker containers** expose ports on localhost and use Docker network internally

---

## Key Files Created

| File | Purpose |
|------|---------|
| `app/config.py` | Smart config (local vs docker detection) |
| `app/adapters/auth.py` | Authentication adapter for MSME Engine |
| `app/adapters/factory.py` | Adapter factory with real service URLs |
| `scripts/simulate_session_workflow.py` | Complete workflow simulation |
| `.env.local` | Local development environment |
| `.env.docker` | Docker Compose environment |
| `DEVELOPMENT.md` | Full development guide |

---

## Adapters Implemented

### **BotSessionServiceAdapter**
```python
adapter = AdapterFactory.get_bot_session_adapter()
await adapter.health_check()
await adapter.fetch_session("sess-123")
```

### **UserBotConversationAdapter**
```python
adapter = AdapterFactory.get_user_bot_session_adapter()
session = await adapter.create_session("260701234567", "BIZ-001", {})
await adapter.close_session(session["session_id"], "reason")
await adapter.get_active_sessions("260701234567")
```

### **AuthenticationAdapter** (NEW)
```python
auth = AuthenticationAdapter()
user_info = await auth.verify_user("260701234567")  # role, business_id, etc.
business = await auth.get_business_profile("BIZ-001")
```

---

## Testing

### Unit Tests (No containers required)
```powershell
pytest app/adapters/tests/test_bot_session.py -v
pytest app/adapters/tests/test_user_bot_session.py -v
```

### Integration Tests (Real services)
```powershell
pytest app/adapters/tests/test_integration_bot_session.py -v -s
```

### Simulation
```powershell
python -m scripts.simulate_session_workflow
```

---

## Next Phase

**Phase 1.1: Implement Remaining Backend Adapters**
- Catalog/Inventory Adapter
- Cart/Order Adapter
- Payment/Revenue Adapter
- Delivery Adapter
- Affiliate Adapter
- MSME Engine Adapter

Each will follow the same pattern:
1. Map backend service endpoints
2. Create adapter interface in `base.py`
3. Implement adapter with real HTTP calls
4. Add unit tests
5. Add to `factory.py`

---

## Environment Variables Quick Reference

| Variable | Local Value | Docker Value |
|----------|------------|--------------|
| `ENVIRONMENT` | `local` | `docker` |
| `BOT_SESSION_URL` | `http://localhost:8000` | `http://bot-session:8000` |
| `MSME_ENGINE_URL` | `http://localhost:8500` | `http://msme-engine:8500` |
| `REDIS_URL` | `redis://localhost:6379/0` | `redis://redis:6379/0` |
| `DATABASE_URL` | `@localhost:5432` | `@postgres:5432` |

**Automatic:** Just set `ENVIRONMENT=local` and config defaults to localhost!

---

## Status

✅ **Phase 1.0 Bot Session Adapters:** COMPLETE
- Infrastructure adapter (bot-session)
- User-bot conversation adapter
- Auth adapter (MSME Engine)
- Factory pattern with real service URLs
- Comprehensive tests (25+ test cases)
- Workflow simulation

🔲 **Phase 1.1:** Next - Implement remaining backend adapters
🔲 **Phase 2:** Persistence & Cache Layer
🔲 **Phase 3:** Orchestration Layer
🔲 **Phase 4:** Bot-Facing API

---

## Quick Troubleshooting

**Port already in use?**
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000
# Kill process if needed
taskkill /PID <PID> /F
```

**Docker container won't start?**
```powershell
# Check logs
docker-compose logs bot-session

# Restart
docker-compose restart bot-session
```

**Connection refused?**
```powershell
# Verify Docker is running
docker ps

# Verify ports are exposed
docker-compose port bot-session 8000

# Test connection
curl http://localhost:8000/health
```

---

**Ready to code!** 🚀
