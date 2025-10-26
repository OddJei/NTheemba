const Logger = require('./Logger');

const logger = new Logger();

function logEvent(event, status, message, extra = {}) {
  logger.log(event, status, message, extra);
}

module.exports = { logEvent };
