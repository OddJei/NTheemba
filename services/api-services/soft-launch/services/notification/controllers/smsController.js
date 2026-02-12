const crypto = require('crypto');
const { loadDb, saveDb } = require('../storage/db');
const logger = require('../utils/logger');

function _newId() {
  return `ntf_${crypto.randomBytes(12).toString('hex')}`;
}

function _nowIso() {
  return new Date().toISOString();
}

exports.handleSMS = async (req, res) => {
  const { to, message, recipients, user_id, business_id, template } = req.body;
  const recips = Array.isArray(recipients)
    ? recipients
    : to
      ? [to]
      : [];

  if (!recips.length || !message) {
    return res.status(400).json({ ok: false, error: 'missing to/message' });
  }

  const id = _newId();
  const record = {
    id,
    user_id: user_id || null,
    business_id: business_id || null,
    channel: 'sms',
    template: template || null,
    payload: { to, recipients: recips, message },
    status: 'pending',
    error_message: null,
    retry_count: 0,
    created_at: _nowIso(),
    sent_at: null,
    failed_at: null,
    next_retry_at: null
  };

  try {
    // Persist to queue (no immediate send)
    const db = loadDb();
    db.notifications.push(record);
    saveDb(db);

    logger.info('SMS queued for delivery', { id, recipients: recips.length, message: message.substring(0, 50) });
    
    // Return immediately with pending status
    // Background worker will process and send async
    return res.status(201).json({ ok: true, id, status: 'pending', message: 'SMS queued' });
  } catch (err) {
    logger.error('handleSMS error', err && err.message ? err.message : err);
    return res.status(500).json({ ok: false, error: 'queue_failed' });
  }
};
