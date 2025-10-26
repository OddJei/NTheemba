const express = require('express');
const router = express.Router();
const emailCtrl = require('../controllers/emailController');
const smsCtrl = require('../controllers/smsController');

router.post('/email', emailCtrl.handleEmail);
router.post('/sms', smsCtrl.handleSMS);

router.get('/ping', (req, res) => res.json({ ok: true, service: 'notifier' }));

module.exports = router;
