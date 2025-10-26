const QueueManager = require('../PulseGrid/core/QueueManager');
const Strategy = require('../PulseGrid/core/Strategy');
const Limiter = require('../PulseGrid/core/Limiter');
const Dispatcher = require('../PulseGrid/core/Dispatcher');
const PulseGrid = require('../PulseGrid/core/PulseGrid');
const { logEvent } = require('../PulseGrid/services/log');
const { activeSessions } = require('../models/Session');
const Redis = require("ioredis");
// Use REDIS_URL from environment for local/dev overrides. Fall back to localhost for safety.
const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
const fs = require("fs");
const path = require("path");
const axios = require("axios");

const toDataUrl = async (source) => {
  if (source.startsWith("data:image/")) {
    return source; // already a Data URL
  }

  let buffer, mime;

  if (source.startsWith("http")) {
    const response = await axios.get(source, { responseType: "arraybuffer" });
    buffer = Buffer.from(response.data, "binary");
    mime = response.headers["content-type"];
  } else {
    const ext = path.extname(source).slice(1); // e.g. 'jpg'
    mime = `image/${ext}`;
    buffer = fs.readFileSync(source);
  }

  return `data:${mime};base64,${buffer.toString("base64")}`;
};

// 🧠 Dynamic sender connected to live sessions
const OpenWASender = {
/*************  ✨ Windsurf Command ⭐  *************/
/**
 * Send a message to a recipient using OpenWA session
 * @param {string} sessionKey - OpenWA session key
 * @param {string} recipient - Phone number or username of recipient
 * @param {string|object} message - Message to send, either a string or an object with image_url and caption
 * @returns {Promise<boolean>} True if message sent successfully, false otherwise

/*******  5eca6a5f-d4de-4889-a847-fc9a63f62bf8 *******/
  async send(sessionKey, recipient, message) {
    const sessionService = require('./sessionService');
    const client = sessionService.getSession(sessionKey);
    
    if (!client) {
      logEvent("pulsegrid_send_skip", "warn", `Session ${sessionKey} not ready. Skipping message.`);
      return false;
    }

    try {
      const normalized = recipient.endsWith('@c.us') ? recipient : recipient.replace(/\D/g, '') + '@c.us';

      if (typeof message === 'string') {
        await client.sendText(normalized, message);
      } else if (typeof message === 'object' && message !== null) {

        const dataUrl = await toDataUrl(message.image_url);

        await client.sendImage(
          normalized,
          dataUrl,
          'img.jpg',
          message.caption || '',
          message.view_once || false
        );
      } else {
        throw new Error("Unsupported message format");
      }

      logEvent("pulsegrid_send", "success", `Sent message to ${normalized}`, { sessionKey });
      return true;
    } catch (err) {
      logEvent("pulsegrid_send_fail", "error", `Failed to send via OpenWA`, {
        sessionKey,
        recipient,
        error: err.message
      });
      return false;
    }
  }
};

const queue = new QueueManager();
const strategy = new Strategy(10); // recipients per pulse
const limiter = new Limiter();
const dispatcher = new Dispatcher(queue, OpenWASender, strategy, limiter);
const pulsegrid = new PulseGrid(dispatcher, 2000); // every 2s

let pulsegridStarted = false;

class PulseGridService {
  startPulseGrid() {
    if (pulsegridStarted) return;
    pulsegridStarted = true;
    logEvent("pulsegrid_start", "info", "🚀 PulseGrid initialized");
    pulsegrid.start();
  }

  async startQueuePump() {
    console.log("🚀 Queue pump started. Listening to Redis...");

    while (true) {
      try {
        const result = await redis.blpop("ntheemba:outgoing", 0);
        const payload = JSON.parse(result[1]);

        const { to, from, session_id, business_id, reply, meta } = payload;

        // Find active WhatsApp client for this business
        const sessionService = require('./sessionService');
        const activeSessions = sessionService.getAllActiveSessions();
        
        // Find session key that matches this business
        let client = null;
        let sessionKey = null;
        
        for (const [key, sessionClient] of Object.entries(activeSessions)) {
          if (key.startsWith(`${business_id}-`)) {
            client = sessionClient;
            sessionKey = key;
            break;
          }
        }

        if (!client) {
          console.error(`❌ No active WhatsApp client found for business ${business_id}`);
          continue;
        }

        // Transform the payload for PulseGrid
        const pulsegridPayload = {
          session_id: sessionKey,  // Use the WhatsApp session key
          recipient: to,
          message: reply
        };

        queue.add(pulsegridPayload.session_id, pulsegridPayload.recipient, pulsegridPayload.message);
        console.log(`✅ Enqueued message for ${pulsegridPayload.recipient} via business ${business_id} (session: ${sessionKey})`);
      } catch (err) {
        console.error("❌ Failed to dequeue or enqueue:", err.message);
      }
    }
  }

  async sendMessage(sessionId, recipient, message) {
    return await OpenWASender.send(sessionId, recipient, message);
  }

  async getSessionMessages(sessionId) {
    // Get messages for a session - could be implemented based on PulseGrid API
    return [];
  }

  async getRecipientQueue(sessionId, recipient) {
    // Get queued messages for a recipient - could be implemented based on PulseGrid API
    return [];
  }
}

module.exports = new PulseGridService();