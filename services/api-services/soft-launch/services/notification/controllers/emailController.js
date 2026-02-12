const crypto = require('crypto');
const { loadDb, saveDb } = require('../storage/db');
const logger = require('../utils/logger');

function _newId() {
  return `ntf_${crypto.randomBytes(12).toString('hex')}`;
}

function _nowIso() {
  return new Date().toISOString();
}

exports.handleEmail = async (req, res) => {
  const { to, subject, message, html, user_id, business_id, template } = req.body;
  if (!to || !subject || (!message && !html)) {
    return res.status(400).json({ ok: false, error: 'missing to/subject/message' });
  }

  const id = _newId();
  const record = {
    id,
    user_id: user_id || null,
    business_id: business_id || null,
    channel: 'email',
    template: template || null,
    payload: { to, subject, message, html },
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

    logger.info('Email queued for delivery', { id, to, subject });
    
    // Return immediately with pending status
    // Background worker will process and send async
    return res.status(201).json({ ok: true, id, status: 'pending', message: 'Email queued' });
  } catch (err) {
    logger.error('handleEmail error', err && err.message ? err.message : err);
    return res.status(500).json({ ok: false, error: 'queue_failed' });
  }
};
