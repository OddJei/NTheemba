const crypto = require('crypto');

const { loadDb, saveDb } = require('../storage/db');
const { sendSMS } = require('../services/smsService');
const { sendEmail } = require('../services/emailService');

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
    status: 'created',
    error_message: null,
    created_at: createdAt,
    sent_at: null
  };

  const db = loadDb();
  db.notifications.push(record);
  saveDb(db);

  try {
    if (normalizedChannel === 'sms') {
      const to = payload && payload.to ? payload.to : undefined;
      const recipients = payload && Array.isArray(payload.recipients) ? payload.recipients : undefined;
      const message = payload && payload.message ? payload.message : undefined;
      await sendSMS({ to, recipients, message });
    } else if (normalizedChannel === 'email') {
      const to = payload && payload.to ? payload.to : undefined;
      const subject = payload && payload.subject ? payload.subject : undefined;
      const message = payload && payload.message ? payload.message : undefined;
      const html = payload && payload.html ? payload.html : undefined;
      if (!to || !subject || (!message && !html)) {
        throw new Error('missing_email_payload');
      }
      await sendEmail({ to, subject, text: message, html });
    } else {
      return res.status(400).json({ detail: 'unsupported channel' });
    }

    // update record status
    const db2 = loadDb();
    const idx = db2.notifications.findIndex((n) => n.id === id);
    if (idx >= 0) {
      db2.notifications[idx].status = 'sent';
      db2.notifications[idx].sent_at = _nowIso();
      saveDb(db2);
      return res.status(201).json(db2.notifications[idx]);
    }

    return res.status(201).json({ ...record, status: 'sent', sent_at: _nowIso() });
  } catch (err) {
    const msg = err && err.message ? err.message : String(err);
    const db2 = loadDb();
    const idx = db2.notifications.findIndex((n) => n.id === id);
    if (idx >= 0) {
      db2.notifications[idx].status = 'failed';
      db2.notifications[idx].error_message = msg;
      saveDb(db2);
      return res.status(201).json(db2.notifications[idx]);
    }

    return res.status(201).json({ ...record, status: 'failed', error_message: msg });
  }
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
