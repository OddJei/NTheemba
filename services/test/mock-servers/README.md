# NTheemba Mock Servers

Mock-first development environment for SMS/OTP and Payment gateway integrations.

## Overview

This directory contains mock servers that simulate:
- **SMS/OTP Service** (Port 5101) - Twilio-compatible API
- **Payment Gateway** (Port 5102) - PrimeNet-compatible API for MTN/Airtel/Zamtel

## Quick Start

### Start Both Servers
```bash
cd services/test
python run_mock_servers.py
```

### Start Individual Servers
```bash
# SMS Mock Server
python mock-servers/sms_mock_server.py

# Payment Mock Server
python mock-servers/payment_mock_server.py
```

## SMS Mock Server (Port 5101)

### Endpoints
- `GET /health` - Health check
- `POST /api/v1/messages` - Send SMS (Twilio-compatible)
- `POST /api/v1/verify` - Send OTP verification
- `POST /api/v1/verify/check` - Check OTP code
- `GET /logs` - List log files
- `GET /logs/<filename>` - View specific log file
- `POST /reset` - Reset mock data

### Test SMS Sending
```bash
curl -X POST http://localhost:5101/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+260971234567",
    "body": "Hello from NTheemba!"
  }'
```

### Test OTP Verification
```bash
# Send OTP
curl -X POST http://localhost:5101/api/v1/verify \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+260971234567",
    "channel": "sms"
  }'

# Check OTP (use code from logs)
curl -X POST http://localhost:5101/api/v1/verify/check \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+260971234567",
    "code": "123456"
  }'
```

## Payment Mock Server (Port 5102)

### Endpoints
- `GET /health` - Health check
- `POST /api/v1/payments/initiate` - Initiate payment
- `GET /api/v1/payments/<transaction_id>` - Get payment status
- `POST /api/v1/payments/<transaction_id>/complete` - Manually complete payment
- `GET /api/v1/accounts/<phone>` - Get test account balance
- `POST /api/v1/accounts/<phone>/topup` - Add balance to test account
- `GET /payments` - List all payments
- `GET /stats` - Payment statistics
- `GET /logs` - List log files
- `GET /logs/<filename>` - View specific log file
- `POST /reset` - Reset mock data

### Test Payment Initiation
```bash
curl -X POST http://localhost:5102/api/v1/payments/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 50.00,
    "currency": "ZMW",
    "phone": "260971234567",
    "provider": "mtn",
    "reference": "ORDER_123",
    "webhook_url": "http://localhost:8000/webhooks/payment"
  }'
```

### Test Accounts
- **MTN**: `260971234567` (Balance: ZMW 1000.00)
- **Airtel**: `260961234567` (Balance: ZMW 500.00)
- **Zamtel**: `260951234567` (Balance: ZMW 200.00)

### Check Account Balance
```bash
curl http://localhost:5102/api/v1/accounts/260971234567
```

### Add Test Balance
```bash
curl -X POST http://localhost:5102/api/v1/accounts/260971234567/topup \
  -H "Content-Type: application/json" \
  -d '{"amount": 100.00}'
```

## Configuration

Both servers support runtime configuration via `/config` endpoint:

### SMS Server Config
```bash
curl http://localhost:5101/config
```

### Payment Server Config
```bash
curl http://localhost:5102/config
```

## Logs and Monitoring

### View Logs
```bash
# SMS logs
curl http://localhost:5101/logs

# Payment logs
curl http://localhost:5102/logs
```

### View Specific Log File
```bash
curl http://localhost:5101/logs/sms_events-2024-01-15.jsonl
```

## Integration with Main Services

### Environment Variables
Set these in your `.env` file for local development:

```env
# SMS Service
SMS_BASE_URL=http://localhost:5101
SMS_API_KEY=test_key

# Payment Service
PAYMENT_BASE_URL=http://localhost:5102
PAYMENT_API_KEY=test_key
```

### Switching to Production
When ready for production, update the environment variables to point to real services:

```env
# Real SMS (Twilio/360Dialog)
SMS_BASE_URL=https://api.twilio.com
SMS_API_KEY=your_real_key

# Real Payment (PrimeNet)
PAYMENT_BASE_URL=https://api.primenet.co.zm
PAYMENT_API_KEY=your_real_key
```

## Testing

### Automated Testing
```bash
# Run integration tests with mock servers
python run_integration.py
```

### Manual Testing
1. Start mock servers: `python run_mock_servers.py`
2. Test SMS sending and OTP verification
3. Test payment initiation and completion
4. Check logs for detailed event tracking
5. Reset mock data between test runs: `POST /reset`

## Features

### SMS Mock Server
- ✅ Twilio-compatible API
- ✅ OTP generation and verification
- ✅ Message logging and delivery simulation
- ✅ Configurable success rates and delays
- ✅ Webhook support for delivery receipts

### Payment Mock Server
- ✅ PrimeNet-compatible API for MTN/Airtel/Zamtel
- ✅ Automatic payment completion simulation
- ✅ Test account management with balances
- ✅ Webhook notifications for payment events
- ✅ Configurable success rates per provider
- ✅ Manual payment completion for testing

## Troubleshooting

### Port Conflicts
If ports 5101 or 5102 are in use:
1. Kill processes using those ports
2. Or modify the port numbers in the server files

### Server Won't Start
- Check Python version (requires 3.8+)
- Install dependencies: `pip install flask requests`
- Check file permissions

### Webhooks Not Working
- Ensure your application is running and accessible
- Check webhook URLs in server logs
- Verify firewall settings allow local connections

## Development Notes

- Mock servers automatically simulate realistic delays and failure rates
- All events are logged for debugging and testing
- Test accounts have predefined balances for consistent testing
- Configuration is persisted between server restarts
- Both servers support graceful shutdown with Ctrl+C