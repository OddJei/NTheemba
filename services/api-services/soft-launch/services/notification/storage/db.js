const fs = require('fs');
const path = require('path');
const config = require('../config');

function _ensureDir(filePath) {
  const dir = path.dirname(path.resolve(filePath));
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function loadDb() {
  const file = config.dbFile;
  try {
    if (!fs.existsSync(file)) {
      return { notifications: [] };
    }
    const raw = fs.readFileSync(file, 'utf8');
    const data = JSON.parse(raw || '{}');
    return {
      notifications: Array.isArray(data.notifications) ? data.notifications : []
    };
  } catch {
    return { notifications: [] };
  }
}

function saveDb(db) {
  const file = config.dbFile;
  _ensureDir(file);
  fs.writeFileSync(file, JSON.stringify(db, null, 2), 'utf8');
}

module.exports = { loadDb, saveDb };
