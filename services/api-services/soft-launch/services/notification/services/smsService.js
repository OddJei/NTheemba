const axios = require('axios');
const config = require('../config');
const logger = require('../utils/logger');

async function _sendTextBee({ recipients, message }) {
  const baseUrl = config.sms.textbee.baseUrl;
  const apiKey = config.sms.textbee.apiKey;
  const deviceId = config.sms.textbee.deviceId;

  if (!apiKey || !deviceId) {
    throw new Error('textbee_missing_credentials');
  }

  const url = `${baseUrl}/gateway/devices/${deviceId}/send-sms`;
  const response = await axios.post(
    url,
    { recipients, message },
    { headers: { 'x-api-key': apiKey } }
  );

  return response.data;
}

async function sendSMS({ to, message, recipients }) {
  const recips = Array.isArray(recipients)
    ? recipients
    : to
      ? [to]
      : [];

  if (!recips.length || !message) {
    throw new Error('missing_recipients_or_message');
  }

  const provider = (config.sms.provider || 'mock').toLowerCase();

  if (provider === 'textbee') {
    logger.info('smsService.sendSMS', { provider: 'textbee', recipients: recips.length });
    return _sendTextBee({ recipients: recips, message });
  }

  logger.info('smsService.sendSMS (mock)', { recipients: recips, message });
  return {
    ok: true,
    provider: 'mock',
    recipients: recips,
    message,
    timestamp: new Date().toISOString()
  };
}

module.exports = { sendSMS };
