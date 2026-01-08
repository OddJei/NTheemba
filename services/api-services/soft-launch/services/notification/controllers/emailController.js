const { sendEmail } = require('../services/emailService');
const logger = require('../utils/logger');

exports.handleEmail = async (req, res) => {
  const { to, subject, message, html } = req.body;
  if (!to || !subject || (!message && !html)) {
    return res.status(400).json({ ok: false, error: 'missing to/subject/message' });
  }

  try {
    await sendEmail({ to, subject, text: message, html });
    return res.status(200).json({ ok: true, message: 'Email sent' });
  } catch (err) {
    logger.error('handleEmail error', err && err.message ? err.message : err);
    return res.status(500).json({ ok: false, error: 'email_failed' });
  }
};
