const { loadDb, saveDb } = require('../storage/db');
const crypto = require('crypto');

function _nowIso() {
  return new Date().toISOString();
}

function _getSecret() {
  return (process.env.OUTBOX_INTERNAL_SECRET || '').trim();
}

function _checkSecret(req) {
  const expected = _getSecret();
  if (!expected) return true;
  const provided = (req.headers['x-internal-secret'] || '').trim();
  return expected && provided && expected === provided;
}

async function pending(req, res) {
  if (!_checkSecret(req)) return res.status(401).json({ detail: 'invalid_internal_secret' });
  const db = loadDb();
  const now = new Date();
  const rows = (db.outbox || []).filter((r) => r.status === 'pending' && (!r.send_after || new Date(r.send_after) <= now));
  const out = rows.map((r) => ({
    id: r.id,
    event_type: r.topic,
    payload: r.payload,
    dedupe_key: r.dedupe_key,
    destination: r.destination,
    attempts: r.attempts || 0,
    scheduled_at: r.send_after || null,
    correlation_id: (r.payload && r.payload.correlation_id) || null,
  }));
  return res.json(out);
}

async function ack(req, res) {
  if (!_checkSecret(req)) return res.status(401).json({ detail: 'invalid_internal_secret' });
  const ids = (req.body && req.body.ids) || [];
  if (!Array.isArray(ids)) return res.status(400).json({ detail: 'ids must be an array' });
  const db = loadDb();
  const acked = [];
  ids.forEach((id) => {
    const idx = (db.outbox || []).findIndex((o) => o.id === id);
    if (idx >= 0) {
      db.outbox[idx].status = 'sent';
      db.outbox[idx].sent_at = _nowIso();
      acked.push(id);
    }
  });
  if (acked.length) saveDb(db);
  return res.json({ acked });
}

module.exports = { pending, ack };
