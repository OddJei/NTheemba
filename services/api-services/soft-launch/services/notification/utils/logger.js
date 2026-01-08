const debugEnabled = process.env.DEBUG === '1' || process.env.DEBUG === 'true';

function info(...args) {
  console.log('[INFO]', ...args);
}
function warn(...args) {
  console.warn('[WARN]', ...args);
}
function error(...args) {
  console.error('[ERROR]', ...args);
}
function dbg(...args) {
  if (debugEnabled) console.debug('[DBG]', ...args);
}

module.exports = { info, warn, error, debug: dbg };
