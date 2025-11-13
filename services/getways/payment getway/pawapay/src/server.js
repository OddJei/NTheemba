require('dotenv').config();
const express = require('express');
const bodyParser = require('express').json;
const pawapayRouter = require('./routes/pawapay');

const app = express();
app.use(bodyParser());

app.get('/healthz', (req, res) => res.json({ status: 'ok' }));
app.use('/pawapay', pawapayRouter);

const PORT = process.env.PORT || 4001;
app.listen(PORT, () => {
  console.log(`Pawapay gateway scaffold listening on http://localhost:${PORT}`);
});
