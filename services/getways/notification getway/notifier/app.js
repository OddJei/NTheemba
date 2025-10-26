const express = require('express');
const notifyRoutes = require('./routes/notifyRoutes');
const logger = require('./utils/logger');
require('dotenv').config();

const app = express();
app.use(express.json());

app.use('/notify', notifyRoutes);

app.get('/', (req, res) => res.json({ ok: true, service: 'notifier' }));

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => logger.info(`Notifier running on port ${PORT}`));

module.exports = app;
