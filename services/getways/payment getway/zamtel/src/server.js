require('dotenv').config();
const express = require('express');
const bodyParser = require('express').json;
const zamtelRouter = require('./routes/zamtel');

const app = express();
app.use(bodyParser());

app.get('/healthz', (req, res) => res.json({ status: 'ok' }));
app.use('/zamtel', zamtelRouter);

const PORT = process.env.PORT || 4004;
app.listen(PORT, () => {
  console.log(`Zamtel gateway scaffold listening on http://localhost:${PORT}`);
});
