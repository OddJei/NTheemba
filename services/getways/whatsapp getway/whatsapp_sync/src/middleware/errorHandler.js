// Global error handler middleware
const errorHandler = (err, req, res, next) => {
  console.error(err.stack);

  // Log error
  const logger = require('../utils/logger');
  logger.error('Unhandled error', {
    error: err.message,
    stack: err.stack,
    url: req.url,
    method: req.method
  });

  // Don't leak error details in production
  res.status(500).json({
    error: process.env.NODE_ENV === 'production'
      ? 'Internal server error'
      : err.message
  });
};

module.exports = errorHandler;