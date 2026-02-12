const express = require('express');
require('dotenv').config();

const notifyRoutes = require('./routes/notifyRoutes');
const notificationRoutes = require('./routes/notificationRoutes');
const { startWorker } = require('./workers/notificationWorker');

const app = express();
app.use(express.json());

app.get('/health', (req, res) => res.json({ status: 'ok' }));
app.use('/notify', notifyRoutes);
app.use('/notification', notificationRoutes);

app.get('/', (req, res) => res.json({ ok: true, service: 'softlaunch-notification' }));

if (require.main === module) {
  const PORT = process.env.PORT || 8570;
  const HOST = process.env.HOST || '127.0.0.1';
  
  // Start background worker before listening
  startWorker();
  
  app.listen(PORT, HOST, () => {
    // eslint-disable-next-line no-console
    console.log(`notification service running on http://${HOST}:${PORT}`);
  });
}

module.exports = app;
