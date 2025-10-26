const express = require('express');
const router = express.Router();
const whatsappSyncService = require('../services/whatsappSyncService');

// POST /sync_number → Start or resume session
router.post('/sync_number', async (req, res) => {
  try {
    const result = await whatsappSyncService.startSync(req.body);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET /get_qrd/:sessionId → Serve QR code image
router.get('/get_qrd/:sessionId', async (req, res) => {
  try {
    const result = await whatsappSyncService.getQRCode(req.params.sessionId);
    if (result) {
      res.sendFile(result.filePath);
    } else {
      res.status(404).json({ error: 'QR code not found or expired' });
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET /session_status/:sessionId → Check session status
router.get('/session_status/:sessionId', async (req, res) => {
  try {
    const result = await whatsappSyncService.getSessionStatus(req.params.sessionId);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE /qr/:sessionId → Manually delete QR code
router.delete('/qr/:sessionId', async (req, res) => {
  try {
    const result = await whatsappSyncService.deleteQRCode(req.params.sessionId);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;