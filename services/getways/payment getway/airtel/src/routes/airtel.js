const express = require('express');
const router = express.Router();
const AirtelAdapter = require('../services/airtelAdapter');

const adapter = new AirtelAdapter();

router.post('/charge', async (req, res) => {
  try {
    const payload = req.body;
    const result = await adapter.initiatePayment(payload);
    res.json(result);
  } catch (err) {
    console.error('airtel charge error', err);
    res.status(500).json({ error: 'charge failed', details: err.message });
  }
});

router.post('/verify', async (req, res) => {
  try {
    const { transaction_ref } = req.body;
    const result = await adapter.verifyPayment(transaction_ref);
    res.json(result);
  } catch (err) {
    console.error('airtel verify error', err);
    res.status(500).json({ error: 'verify failed', details: err.message });
  }
});

module.exports = router;
