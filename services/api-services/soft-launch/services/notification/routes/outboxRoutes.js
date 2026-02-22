const express = require('express');
const router = express.Router();
const ctrl = require('../controllers/outboxController');

router.get('/pending', ctrl.pending);
router.post('/ack', ctrl.ack);

module.exports = router;
