const crypto = require('crypto');

const { loadDb, saveDb } = require('../storage/db');
const config = require('../config');

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

  // Accept only whatsapp, email, push
  if (!['whatsapp', 'email', 'push'].includes(normalizedChannel)) {
    return res.status(400).json({ detail: 'unsupported channel - allowed: whatsapp,email,push' });
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
  if (normalizedChannel === 'email') {
    const to = payload && payload.to ? payload.to : undefined;
    const subject = payload && payload.subject ? payload.subject : undefined;
    const message = payload && payload.message ? payload.message : undefined;
    const html = payload && payload.html ? payload.html : undefined;

    if (!to || !subject || (!message && !html)) {
      return res.status(400).json({ detail: 'email requires to, subject, and message or html' });
    }
  } else if (normalizedChannel === 'whatsapp') {
    const to = payload && payload.to ? payload.to : undefined;
    const text = payload && (payload.message || payload.text) ? (payload.message || payload.text) : undefined;
    if (!to || !text) {
      return res.status(400).json({ detail: 'whatsapp requires to and message/text' });
    }
  } else if (normalizedChannel === 'push') {
    const to = payload && (payload.to || payload.device_token || payload.user_id) ? (payload.to || payload.device_token || payload.user_id) : undefined;
    const text = payload && (payload.message || payload.text) ? (payload.message || payload.text) : undefined;
    if (!to || !text) {
      return res.status(400).json({ detail: 'push requires to (user/device) and message/text' });
    }
  }

  // Persist notification to queue (no immediate send)
  const db = loadDb();
  db.notifications.push(record);

  // For whatsapp and push, create an outbox record for dispatcher/ICE
  if (!db.outbox) db.outbox = [];
  if (normalizedChannel === 'whatsapp' || normalizedChannel === 'push') {
    const outId = `outbox_${crypto.randomBytes(12).toString('hex')}`;
    const topic = normalizedChannel === 'whatsapp' ? 'notification.whatsapp' : 'notification.push';
    const destBase = normalizedChannel === 'whatsapp' ? (config.iceBaseUrl || 'http://ice-service:8100') : (config.webBaseUrl || 'http://web:8900');
    const destination = normalizedChannel === 'whatsapp' ? `${destBase}/notifications/whatsapp` : `${destBase}/notifications/push`;

    const outPayload = normalizedChannel === 'whatsapp'
      ? {
          request_id: id,
          to: payload.to,
          from: payload.from || null,
          text: payload.message || payload.text,
          meta: { platform: 'whatsapp', business_id: business_id }
        }
      : {
          request_id: id,
          to: payload.to || payload.device_token || payload.user_id,
          text: payload.message || payload.text,
          meta: { platform: 'push', business_id: business_id }
        };

    const outRecord = {
      id: outId,
      topic,
      dedupe_key: id,
      destination,
      payload: outPayload,
      status: 'pending',
      attempts: 0,
      last_error: null,
      send_after: null,
      created_at: _nowIso()
    };

    db.outbox.push(outRecord);
  }

  saveDb(db);

  // Return immediately with pending status
  return res.status(201).json(record);
}

function handleReceipts(req, res) {
  const body = req.body;
  const receipts = Array.isArray(body) ? body : [body];
  const db = loadDb();
  const updated = [];

  receipts.forEach((rc) => {
    const id = rc.id || rc.request_id || rc.notification_id;
    if (!id) return;
    const idx = db.notifications.findIndex((n) => n.id === id);
    if (idx < 0) return;
    const n = db.notifications[idx];
    if (rc.status) n.status = rc.status;
    if (rc.sent_at) n.sent_at = rc.sent_at;
    if (rc.failed_at) n.failed_at = rc.failed_at;
    if (rc.error_message) n.error_message = rc.error_message;
    if (rc.retry_count !== undefined) n.retry_count = rc.retry_count;
    updated.push(n);
  });

  if (updated.length) saveDb(db);
  return res.json({ updated: updated.length, notifications: updated });
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

module.exports = { sendNotification, getNotification, listUserNotifications, handleReceipts };
