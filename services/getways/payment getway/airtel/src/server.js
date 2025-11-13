require('dotenv').config();
const express = require('express');
const bodyParser = require('express').json;
const airtelRouter = require('./routes/airtel');

const app = express();
app.use(bodyParser());

app.get('/healthz', (req, res) => res.json({ status: 'ok' }));
app.use('/airtel', airtelRouter);

const PORT = process.env.PORT || 4003;
app.listen(PORT, () => {
  console.log(`Airtel gateway scaffold listening on http://localhost:${PORT}`);
});
