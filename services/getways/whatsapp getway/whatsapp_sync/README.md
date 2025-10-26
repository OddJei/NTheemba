# WhatsApp Sync Service

A Node.js service for synchronizing WhatsApp business accounts with the Ntheemba platform.

## Features

- WhatsApp business account synchronization
- QR code generation and management
- Session state management
- PulseGrid message dispatching
- RESTful API endpoints

## Installation

```bash
npm install
```

## Configuration

Copy `.env.example` to `.env` and configure your environment variables:

```bash
cp .env.example .env
```

## Usage

### Development

```bash
npm run dev
```

### Production

```bash
npm start
```

## API Endpoints

- `POST /whatsapp/sync_number` - Start or resume WhatsApp sync session
- `GET /whatsapp/qr/:sessionId` - Get QR code for session
- `GET /whatsapp/session_status/:sessionId` - Check session status
- `DELETE /whatsapp/qr/:sessionId` - Delete QR code
- `GET /health` - Health check

## Testing

```bash
npm test
```

## Project Structure

```
src/
├── app.js                 # Express app setup
├── server.js              # Server startup
├── routes/                # API routes
├── services/              # Business logic
├── models/                # Data models
├── middleware/            # Express middleware
├── utils/                 # Utilities
├── config/                # Configuration
└── PulseGrid/             # Message dispatching
tests/                     # Test files
scripts/                   # Utility scripts
logs/                      # Application logs
qrcodes/                   # QR code storage
```

## License

MIT