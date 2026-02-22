const logger = require('../utils/logger');
const { loadDb, saveDb } = require('../storage/db');
const { sendEmail } = require('../services/emailService');

/**
 * Background worker that processes pending notifications from queue.
 * Handles delivery through gateways (email, SMS, etc).
 * Retries on failure with exponential backoff.
 */

const RETRY_BACKOFF_MS = 5000; // 5 seconds, exponential
const MAX_RETRIES = 3;
const WORKER_INTERVAL_MS = 10000; // Process every 10 seconds

async function processNotification(notification) {
  const { id, channel, payload, retry_count = 0 } = notification;

  try {
    // Only process email deliveries in this worker. SMS is ignored and
    // channels backed by outbox (whatsapp/push) are handled by the outbox
    // dispatcher. This keeps delivery responsibilities consistent.
    if (channel === 'email') {
      const to = payload && payload.to ? payload.to : undefined;
      const subject = payload && payload.subject ? payload.subject : undefined;
      const message = payload && payload.message ? payload.message : undefined;
      const html = payload && payload.html ? payload.html : undefined;
      
      if (!to || !subject || (!message && !html)) {
        throw new Error('missing_email_payload');
      }
      
      await sendEmail({ to, subject, text: message, html });
    } else {
      // Ignore non-email channels here (sms, whatsapp, push, in_app).
      // Outbox entries are created by the controller for whatsapp/push
      // and will be dispatched by the outbox dispatcher. For SMS we
      // intentionally ignore here as requested.
      logger.info(`Skipping delivery for non-email channel: ${channel}`);
      return;
    }

    // Mark as sent
    const db = loadDb();
    const idx = db.notifications.findIndex((n) => n.id === id);
    if (idx >= 0) {
      db.notifications[idx].status = 'sent';
      db.notifications[idx].sent_at = new Date().toISOString();
      db.notifications[idx].error_message = null;
      db.notifications[idx].retry_count = retry_count;
      saveDb(db);
      logger.info(`Notification ${id} sent successfully`, { channel });
    }
  } catch (err) {
    const msg = err && err.message ? err.message : String(err);
    const nextRetryCount = retry_count + 1;

    if (nextRetryCount >= MAX_RETRIES) {
      // Mark as failed after max retries
      const db = loadDb();
      const idx = db.notifications.findIndex((n) => n.id === id);
      if (idx >= 0) {
        db.notifications[idx].status = 'failed';
        db.notifications[idx].error_message = msg;
        db.notifications[idx].retry_count = nextRetryCount;
        db.notifications[idx].failed_at = new Date().toISOString();
        saveDb(db);
        logger.error(`Notification ${id} failed after ${nextRetryCount} retries`, { 
          channel, 
          error: msg 
        });
      }
    } else {
      // Mark as retry pending
      const db = loadDb();
      const idx = db.notifications.findIndex((n) => n.id === id);
      if (idx >= 0) {
        db.notifications[idx].status = 'retry_pending';
        db.notifications[idx].error_message = msg;
        db.notifications[idx].retry_count = nextRetryCount;
        db.notifications[idx].next_retry_at = new Date(
          Date.now() + RETRY_BACKOFF_MS * Math.pow(2, nextRetryCount - 1)
        ).toISOString();
        saveDb(db);
        logger.warn(`Notification ${id} will retry (attempt ${nextRetryCount})`, { 
          channel, 
          error: msg 
        });
      }
    }
  }
}

async function flushPendingNotifications() {
  try {
    const db = loadDb();
    const now = new Date();

    // Find pending and retry_pending notifications ready to process
    const toProcess = db.notifications.filter((n) => {
      if (n.status === 'pending') return true;
      if (n.status === 'retry_pending') {
        const nextRetry = n.next_retry_at ? new Date(n.next_retry_at) : null;
        return nextRetry && nextRetry <= now;
      }
      return false;
    });

    logger.info(`Processing ${toProcess.length} pending notifications`);

    // Process all pending notifications in parallel
    await Promise.all(toProcess.map((n) => processNotification(n)));
  } catch (err) {
    logger.error('Error flushing pending notifications', {
      error: err && err.message ? err.message : String(err)
    });
  }
}

function startWorker() {
  logger.info('Starting notification worker...');
  
  // Initial flush after 2 seconds
  setTimeout(() => flushPendingNotifications(), 2000);
  
  // Recurring flush every WORKER_INTERVAL_MS
  setInterval(() => flushPendingNotifications(), WORKER_INTERVAL_MS);
}

module.exports = { startWorker, flushPendingNotifications };
