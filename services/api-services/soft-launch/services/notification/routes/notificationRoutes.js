const express = require('express');
const router = express.Router();

const ctrl = require('../controllers/notificationController');

router.post('/send', ctrl.sendNotification);
router.get('/:id', ctrl.getNotification);
router.get('/user/:user_id', ctrl.listUserNotifications);

module.exports = router;
