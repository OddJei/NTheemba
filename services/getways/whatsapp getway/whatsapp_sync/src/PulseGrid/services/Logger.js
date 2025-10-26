// Logger class for PulseGrid
const fs = require('fs');
const path = require('path');

const LOG_FILE = path.join(__dirname, '../../../logs/pulsegrid.log');

class Logger {
  log(event, status, message, extra = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      event,
      status,
      message,
      ...extra
    };

    const line = JSON.stringify(logEntry);
    console.log(`[PulseGrid] ${line}`);

    try {
      fs.appendFileSync(LOG_FILE, line + '\n');
    } catch (error) {
      console.error('Failed to write PulseGrid log:', error);
    }
  }
}

module.exports = Logger;