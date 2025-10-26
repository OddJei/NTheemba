require('dotenv').config();
const app = require('./app');
const logger = require('./utils/logger');
const pulsegridService = require('./services/pulsegridService');

const PORT = process.env.PORT || 8080;

app.listen(PORT, () => {
  logger.info('server_start', `📢 Sync API running on port ${PORT}`);

  // Start PulseGrid queue pump
  pulsegridService.startPulseGrid();
  pulsegridService.startQueuePump().catch(err => {
    logger.error('queue_pump_error', `Failed to start queue pump: ${err.message}`);
  });
});