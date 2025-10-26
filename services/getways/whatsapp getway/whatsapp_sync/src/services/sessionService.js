const { create } = require('@open-wa/wa-automate');
const { ev } = require('@open-wa/wa-automate');
const fs = require('fs');
const axios = require('axios');
const path = require('path');
const crypto = require('crypto');
const Redis = require('ioredis');
const logger = require('../utils/logger');
const { activeSessions } = require('../models/Session');

// Encryption setup
const ENCRYPTION_KEY = Buffer.from(process.env.ENCRYPTION_KEY.trim(), "hex");

// Redis setup
const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379/0');
const INCOMING_QUEUE = process.env.REDIS_INCOMING_QUEUE || 'ntheemba:incoming';

// Event listener for QR codes
ev.onAny((event, value) => {
  if (event.startsWith('qr.')) {
    const sessionId = event.split('qr.')[1];
    const base64Image = value.replace(/^data:image\/png;base64,/, "");
    const qrDir = path.join(__dirname, '../../qrcodes');

    if (!fs.existsSync(qrDir)) {
      fs.mkdirSync(qrDir, { recursive: true });
    }

    const filePath = path.join(qrDir, `${sessionId}.png`);
    fs.writeFileSync(filePath, base64Image, "base64");

    console.log(`📸 [ev.onAny] QR code saved for ${sessionId} at ${filePath}`);
  }
});

// Logging Function
const logEvent = (event, status, message, extra = {}) => {
  logger.log(status, event, message, extra);
};

// Encrypt Session Data
const encryptSessionData = (data) => {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv("aes-256-cbc", ENCRYPTION_KEY, iv);
  let encrypted = cipher.update(JSON.stringify(data), "utf8", "hex");
  encrypted += cipher.final("hex");

  return { iv: iv.toString("hex"), encrypted };
};

// Decrypt Session Data
const decryptSessionData = (sessionData) => {
  if (!sessionData || !sessionData.iv || !sessionData.encrypted) {
    throw new Error("❌ Missing IV or encrypted session data!");
  }

  const iv = Buffer.from(sessionData.iv, "hex");
  const decipher = crypto.createDecipheriv("aes-256-cbc", ENCRYPTION_KEY, iv);
  let decrypted = decipher.update(sessionData.encrypted, "hex", "utf8");
  decrypted += decipher.final("utf8");

  return JSON.parse(decrypted);
};

// Save Session Data Securely
const saveSessionData = (sessionData, sessionId) => {
  const LOG_DIR = path.join(__dirname, '../../session_logs');
  if (!fs.existsSync(LOG_DIR)) {
    fs.mkdirSync(LOG_DIR, { recursive: true });
  }

  const filePath = path.join(LOG_DIR, `session_${sessionId}.json`);
  fs.writeFileSync(filePath, JSON.stringify(encryptSessionData(sessionData)));
  console.log(`✅ Session data saved: ${filePath}`);
};

// Load & Restore Session Data
const loadSessionData = (sessionId) => {
  const LOG_DIR = path.join(__dirname, '../../session_logs');
  const filePath = path.join(LOG_DIR, `session_${sessionId}.json`);
  if (fs.existsSync(filePath)) {
    return decryptSessionData(JSON.parse(fs.readFileSync(filePath, "utf8")));
  }
  return null;
};

// Handle Session State Changes
const handleSessionStateChange = (client, businessId, phoneNumber) => {
  const sessionId = `${businessId}-${phoneNumber}`;

  client.onStateChanged((state) => {
    console.log(`🔄 Session state changed: ${state}`);
    logEvent("session_state_change", "info", `Session state changed to ${state}`, { businessId, phoneNumber });

    if (state === "CONNECTED") {
      // ✅ Session is authenticated — clean up QR
      deleteQrCode(sessionId);
    }

    if (state === "CONFLICT" || state === "UNLAUNCHED") {
      console.warn(`⚠️ Session conflict detected for ${phoneNumber}, terminating...`);
      terminateSession(businessId, phoneNumber, client);
    } else if (state === "DISCONNECTED") {
      console.warn(`⚠️ Session disconnected for ${phoneNumber}, attempting restart...`);
      restartSessions();
    }
  });
};

// Handle Incoming Messages
const handleIncomingMessages = (client) => {
  client.onMessage(async (message) => {
    if (message.type !== "chat") {
      console.log(`🚫 Ignoring non-text message from ${message.from} (type: ${message.type})`);
      return;
    }
    // ignore all messages from groups
    if (message.from.endsWith("@g.us")) {
      console.log(`🚫 Ignoring group message from ${message.from}`);
      return;
    }

    if (message.from.endsWith("@newsletter")) {
      console.log(`🚫 Ignoring group message to ${message.to}`);
      return;
    }

    console.log(`📩 Incoming Message from ${message.from}: ${message.body} to ${message.to}`);
    logEvent("incoming_message", "info", `Received message from ${message.from} to ${message.to}`);

    // Format message for bot service
    const formattedMessage = {
      to: message.to,
      from: message.from,
      request_id: `wa-${message.id}-${Date.now()}`,
      timestamp: new Date().toISOString(),
      message: message.body,
      message_id: message.id,
      meta: {
        platform: "wa"
      }
    };

    try {
      // Push to Redis queue
      await redis.rpush(INCOMING_QUEUE, JSON.stringify(formattedMessage));
      logEvent('Message queued', 'success', `✅ Message from ${message.from} queued for bot processing`);
      console.log(`📨 Message queued to Redis: ${formattedMessage.request_id}`);
    } catch (error) {
      logEvent('Redis queue error', 'error', `❌ Failed to queue message from ${message.from}: ${error.message}`);
      console.error(`❌ Redis queue error:`, error);
    }
  });
};

const delay = (ms) => new Promise((res) => setTimeout(res, ms));
let pulsegridRunning = false;

const deleteQrCode = (sessionId) => {
  const filePath = path.join(__dirname, '../../qrcodes', `${sessionId}.png`);
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
    console.log(`🧹 Deleted QR code for ${sessionId}`);
  }
};

class SessionService {
  async startSession(businessId, phoneNumber) {
    const sessionId = `${businessId}-${phoneNumber}`;
    if (activeSessions[sessionId]) {
      console.log(`✅ Session already active for ${phoneNumber}, skipping start.`);
      return;
    }

    const sessionData = loadSessionData(sessionId);

    const launchConfig = {
      sessionId,
      useChrome: true,
      api_Key: process.env.WHATSAPP_API_KEY,
      qrTimeout: 120000,
      authTimeout: 180000,
      qrRefreshS: 60000,
      killTimer: 0,
      headless: true,
    };

    // 🔁 If a session file exists and was active, try to restore it
    if (sessionData && sessionData.status === "active") {
      try {
        console.log(`✅ Restoring session for ${phoneNumber}...`);
        const client = await create(launchConfig);

        const page = await client.getPage();
        await page.waitForSelector('#app', { timeout: 60000 });

        activeSessions[sessionId] = client;

        if(!pulsegridRunning) {
          const pulsegridService = require('./pulsegridService');
          pulsegridService.startPulseGrid();
          pulsegridService.startQueuePump();
          pulsegridRunning = true;
        }
        handleSessionStateChange(client, businessId, phoneNumber);
        handleIncomingMessages(client);

        console.log(`✅ Session restored and active for ${phoneNumber}`);
        return client;
      } catch (err) {
        console.warn(`⚠️ Failed to restore session for ${phoneNumber}. Falling back to fresh session.`, err.message);
      }
    }

    // 🆕 If no session or restore failed, start a new one
    try {
      console.log(`🔑 Starting new session for ${phoneNumber}...`);
      let client;

      try {
        client = await create(launchConfig);
        const page = await client.getPage();
        await page.waitForSelector('#app', { timeout: 60000 });
      } catch (err) {
        if (err.message.includes("Execution context was destroyed")) {
          console.warn(`⚠️ Context lost for ${phoneNumber} — retrying in 60s...`);
          await delay(60000);
          client = await create(launchConfig);
          const page = await client.getPage();
          await page.waitForSelector('#app', { timeout: 60000 });
        } else {
          throw err;
        }
      }

      console.log(`✅ Session active for ${phoneNumber}`);
      activeSessions[sessionId] = client;

      if(!pulsegridRunning){
        const pulsegridService = require('./pulsegridService');
        pulsegridService.startPulseGrid();
        pulsegridService.startQueuePump();
        pulsegridRunning = true;
      }

      await axios.put(`http://api:8000/synced_businesses/update_status/${businessId}?new_status=active`);
      saveSessionData({ businessId, phoneNumber, sessionId, status: "active" }, sessionId);

      try {
        const res = await axios.get(`http://api:8000/active_sessions/${phoneNumber}`);
        if (res.status === 200 && ["active", "inactive"].includes(res.data.status)) {
          console.log(`✅ DB session already exists for ${phoneNumber}`);
        } else {
          console.log(`ℹ️ Creating new DB session for ${phoneNumber}...`);
          await axios.post(`http://api:8000/active_sessions/create?business_id=${businessId}&phone_number=${phoneNumber}`);
          logEvent("session_created", "success", `✅ Active session created for ${phoneNumber}`, { businessId, phoneNumber });
        }
      } catch (err) {
        console.error(`❌ Error syncing DB session for ${phoneNumber}:`, err.message);
      }

      handleSessionStateChange(client, businessId, phoneNumber);
      handleIncomingMessages(client);
      logEvent("session_start", "success", `✅ Session started for ${businessId}`, { sessionId });

      return client;
    } catch (error) {
      console.error(`❌ Failed to start session for ${businessId}:`, error.message);
      logEvent("session_start_error", "error", `❌ Session failed for ${businessId}`, {
        error: error.message,
        stack: error.stack
      });
    }
  }

  async restartSessions() {
    try {
      const response = await axios.get("http://api:8000/active_sessions/all");
      const inactiveSessions = response.data.inactive_sessions;

      if (!inactiveSessions || inactiveSessions.length === 0) {
        logEvent("session_restart", "info", "✅ No inactive sessions found, skipping restart.");
        return;
      }

      await Promise.all(
        inactiveSessions.map(({ business_id, phone_number }) => {
          logEvent("session_check", "info", `Restarting session for ${business_id}`);
          return this.startSession(business_id, phone_number);
        })
      );

      logEvent("session_restart", "success", "✅ All inactive sessions restarted successfully!");
    } catch (error) {
      logEvent("session_restart_error", "error", "❌ Error checking session states", { error: error.message, stack: error.stack });
    }
  }

  async terminateSession(businessId, phoneNumber, client) {
    try {
      console.log(`⚠️ Terminating session for ${phoneNumber}...`);

      // ✅ Ensure client is properly destroyed
      await client.destroy();
      console.log(`✅ Session destroyed for ${phoneNumber}`);

      // ✅ Update active_sessions to inactive
      await axios.put(`http://api:8000/active_sessions/update_status/${phoneNumber}?new_status=inactive`, {
        headers: { 'Accept': 'application/json' }
      });

      // ✅ Update synced_businesses to inactive
      await axios.put(`http://api:8000/synced_businesses/update_status/${businessId}?new_status=inactive`, {
        headers: { 'Accept': 'application/json' }
      });

      console.log(`✅ Session status updated to inactive for ${phoneNumber}`);
      logEvent("session_terminated", "info", `Session for ${phoneNumber} terminated`, { businessId, phoneNumber });
    } catch (error) {
      console.error(`❌ Failed to terminate session for ${phoneNumber}:`, error.message);
      logEvent("session_termination_error", "error", "❌ Session termination failed", { error: error.message });
    }
  }

  async terminateAllSessions() {
    try {
      const response = await axios.get("http://api:8000/active_sessions/all");
      const activeSessionsList = response.data.active_sessions;

      if (!activeSessionsList || activeSessionsList.length === 0) {
        logEvent("session_termination", "info", "✅ No active sessions found, skipping termination.");
        return;
      }

      await Promise.all(
        activeSessionsList.map(({ business_id, phone_number, client }) => {
          logEvent("session_check", "info", `Terminating session for ${business_id}`);
          return this.terminateSession(business_id, phone_number, client);
        })
      );

      logEvent("session_termination", "success", "✅ All active sessions terminated successfully!");
    } catch (error) {
      logEvent("session_termination_error", "error", "❌ Error checking session states", { error: error.message, stack: error.stack });
    }
  }

  isSessionActive(sessionId) {
    return !!activeSessions[sessionId];
  }

  getSession(sessionId) {
    return activeSessions[sessionId];
  }

  getAllActiveSessions() {
    return activeSessions;
  }
}

module.exports = new SessionService();