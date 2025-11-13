const express = require('express');
const router = express.Router();
const PawapayAdapter = require('../services/pawapayAdapter');

const adapter = new PawapayAdapter();

router.post('/charge', async (req, res) => {
  try {
    const payload = req.body;
    const result = await adapter.initiatePayment(payload);
    res.json(result);
  } catch (err) {
    console.error('charge error', err);
    res.status(500).json({ error: 'charge failed', details: err.message });
  }
});

router.post('/verify', async (req, res) => {
  try {
    const { transaction_ref } = req.body;
    const result = await adapter.verifyPayment(transaction_ref);
    res.json(result);
  } catch (err) {
    console.error('verify error', err);
    res.status(500).json({ error: 'verify failed', details: err.message });
  }
});

module.exports = router;
