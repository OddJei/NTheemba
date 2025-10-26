const fs = require('fs');
const path = require('path');

const LOG_FILE = path.join(__dirname, '../../logs/sync_api_logs.json');

class Logger {
  log(level, event, message, extra = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      event,
      status: level,
      message,
      ...extra
    };

    const line = JSON.stringify(logEntry);
    console.log(line);

    // Append to file
    try {
      fs.appendFileSync(LOG_FILE, line + '\n');
    } catch (error) {
      console.error('Failed to write to log file:', error);
    }
  }

  info(event, message, extra = {}) {
    this.log('info', event, message, extra);
  }

  warn(event, message, extra = {}) {
    this.log('warning', event, message, extra);
  }

  error(event, message, extra = {}) {
    this.log('error', event, message, extra);
  }
}

module.exports = new Logger();