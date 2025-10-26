const express = require('express');
const router = express.Router();

// Import route modules
const whatsappRoutes = require('./whatsapp');
const healthRoutes = require('./health');

// Register routes
router.use('/', whatsappRoutes);
router.use('/health', healthRoutes);

module.exports = router;