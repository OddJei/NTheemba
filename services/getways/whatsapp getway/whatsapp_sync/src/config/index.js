// Main configuration
require('dotenv').config({ path: './config/config.env' });

const config = {
  port: process.env.PORT || 8080,
  apiKey: process.env.WHATSAPP_API_KEY,
  apiBaseUrl: process.env.API_BASE_URL || 'http://api:8000',
  logLevel: process.env.LOG_LEVEL || 'info',
  qrCodeDir: process.env.QR_CODE_DIR || './qrcodes',
  sessionTimeout: parseInt(process.env.SESSION_TIMEOUT) || 3600000, // 1 hour
  maxRetries: parseInt(process.env.MAX_RETRIES) || 3,
  retryDelay: parseInt(process.env.RETRY_DELAY) || 1000
};

module.exports = config;