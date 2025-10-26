# WhatsApp Session Restart Script

This script automatically restarts WhatsApp sessions for all businesses that have been previously synced when the application comes back online after downtime.

## Usage

```bash
# Using npm script
npm run restart-sessions

# Or directly
node restart_sessions.js
```

## What it does

1. **Queries the API** for all businesses with `sync_status = 'active'`
2. **Filters businesses** that have an `owner_phone` number
3. **Starts WhatsApp sessions** for each business using their phone number
4. **Reports results** showing which businesses succeeded/failed

## Configuration

The script uses these environment variables:

- `API_BASE_URL` - Base URL for the API service (default: `http://localhost:8000`)
- `WHATSAPP_SYNC_URL` - Base URL for the WhatsApp sync service (default: `http://localhost:3000`)

## Example Output

```
🔄 Starting session restart process...
🔍 Fetching synced businesses from API...
✅ Found 3 synced businesses

📋 Synced businesses to restart:
  - business_001: +260977001122
  - business_002: +260977002233
  - business_003: +260977003344

🔄 Starting sessions...
🚀 Starting session for business: business_001 (+260977001122)
✅ Session started for business_001: { status: 'pending', ... }
🚀 Starting session for business: business_002 (+260977002233)
✅ Session started for business_002: { status: 'pending', ... }

📊 Session Restart Summary:
✅ Successful: 2
❌ Failed: 1

❌ Failed businesses:
  - business_003: Connection timeout
```

## When to use

Run this script when:

- The WhatsApp sync service restarts after downtime
- Docker containers are restarted
- The application recovers from a crash
- You want to ensure all synced businesses have active WhatsApp sessions

## Requirements

- Node.js >= 18.0.0
- Access to the running API and WhatsApp sync services
- Businesses must have `sync_status = 'active'` and valid `owner_phone` numbers</content>
<parameter name="filePath">c:\Users\SMART PC\Documents\NTheemba\services\whatsapp_sync\SESSION_RESTART_README.md