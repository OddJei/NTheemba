require('dotenv').config();
const express = require('express');
const bodyParser = require('express').json;
const mtnRouter = require('./routes/mtn');

const app = express();
app.use(bodyParser());

app.get('/healthz', (req, res) => res.json({ status: 'ok' }));
app.use('/mtn', mtnRouter);

const PORT = process.env.PORT || 4002;
app.listen(PORT, () => {
  console.log(`MTN gateway scaffold listening on http://localhost:${PORT}`);
});
