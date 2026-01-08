const { sendSMS } = require('../services/smsService');
const logger = require('../utils/logger');

exports.handleSMS = async (req, res) => {
  const { to, message, recipients } = req.body;
  if ((!to && !Array.isArray(recipients)) || !message) {
    return res.status(400).json({ ok: false, error: 'missing to/message' });
  }

  try {
    const result = await sendSMS({ to, message, recipients });
    return res.status(200).json({ ok: true, result });
  } catch (err) {
    logger.error('handleSMS error', err && err.message ? err.message : err);
    return res.status(500).json({ ok: false, error: 'sms_failed' });
  }
};
