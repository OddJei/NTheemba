const crypto = require('crypto');

const { loadDb, saveDb } = require('../storage/db');

function _newId() {
  return `ntf_${crypto.randomBytes(12).toString('hex')}`;
}

function _nowIso() {
  return new Date().toISOString();
}

function _normalizeChannel(channel) {
  return String(channel || '').trim().toLowerCase();
}

async function sendNotification(req, res) {
  const { user_id, business_id, channel, template, payload } = req.body || {};
  const normalizedChannel = _normalizeChannel(channel);

  if (!normalizedChannel) {
    return res.status(400).json({ detail: 'channel required' });
  }

  const id = _newId();
  const createdAt = _nowIso();

  const record = {
    id,
    user_id: user_id || null,
    business_id: business_id || null,
    channel: normalizedChannel,
    template: template || null,
    payload: payload ?? null,
    status: 'pending',
    error_message: null,
    retry_count: 0,
    created_at: createdAt,
    sent_at: null,
    failed_at: null,
    next_retry_at: null
  };

  // Basic validation per channel
  if (normalizedChannel === 'sms') {
    const to = payload && payload.to ? payload.to : undefined;
    const recipients = payload && Array.isArray(payload.recipients) ? payload.recipients : undefined;
    const message = payload && payload.message ? payload.message : undefined;
    
    if (!message || (!to && (!recipients || !recipients.length))) {
      return res.status(400).json({ detail: 'sms requires message and to/recipients' });
    }
  } else if (normalizedChannel === 'email') {
    const to = payload && payload.to ? payload.to : undefined;
    const subject = payload && payload.subject ? payload.subject : undefined;
    const message = payload && payload.message ? payload.message : undefined;
    const html = payload && payload.html ? payload.html : undefined;
    
    if (!to || !subject || (!message && !html)) {
      return res.status(400).json({ detail: 'email requires to, subject, and message or html' });
    }
  } else if (!(normalizedChannel === 'in_app' || normalizedChannel === 'inapp')) {
    return res.status(400).json({ detail: 'unsupported channel' });
  }

  // Persist to queue (no immediate send)
  const db = loadDb();
  db.notifications.push(record);
  saveDb(db);

  // Return immediately with pending status
  // Background worker will process and send async
  return res.status(201).json(record);
}

function getNotification(req, res) {
  const { id } = req.params;
  const db = loadDb();
  const n = db.notifications.find((x) => x.id === id);
  if (!n) return res.status(404).json({ detail: 'notification not found' });
  return res.json(n);
}

function listUserNotifications(req, res) {
  const { user_id } = req.params;
  const db = loadDb();
  const rows = db.notifications
    .filter((x) => x.user_id === user_id)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  return res.json(rows);
}

module.exports = { sendNotification, getNotification, listUserNotifications };
