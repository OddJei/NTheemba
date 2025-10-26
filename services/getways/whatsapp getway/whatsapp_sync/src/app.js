const express = require('express');
const routes = require('./routes');
const { requireApiKey } = require('./middleware/auth');

const app = express();

// Middleware
app.use(express.json());

// API Key middleware for all routes
app.use(requireApiKey);

// Routes
app.use('/', routes);

// Global error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

module.exports = app;