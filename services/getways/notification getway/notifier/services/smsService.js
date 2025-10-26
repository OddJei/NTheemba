const logger = require('../utils/logger');

async function sendSMS({ to, message }) {
  logger.info('smsService.sendSMS (mock)', { to, message });

  // Simulate delivery delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Log to console as if sent
  console.log(`[MOCK SMS] To: ${to} | Message: ${message}`);

  return {
    ok: true,
    provider: 'mock',
    to,
    message,
    timestamp: new Date().toISOString()
  };
}

module.exports = { sendSMS };
