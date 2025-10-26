const express = require('express');
const router = express.Router();

// GET /health → Health check
router.get('/', (req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

module.exports = router;