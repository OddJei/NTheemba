/**
 * code.gs - TradeFlow Pro Backend
 * Complete server-side implementation for Google Apps Script
 */

// ============================================================
// 1. DEPLOYMENT & ASSETS
// ============================================================

const CAPTURE_RUNTIME_URL = 'https://nds-capture-runtime.onrender.com';
const APP_STATE_CHUNK_SIZE = 45000;
const APP_STATE_CHUNK_COUNT_SUFFIX = '__chunk_count';
const APP_STATE_CHUNK_SUFFIX = '__chunk_';
const TRADEFLOW_INSTALLATION = {
  product: 'tradeflow',
  edition: 'pro',
  clientId: 'CLIENT-CODE',
  clientName: 'Client Business Name',
  branchName: 'Main Branch',
  installationId: 'TF-CLIENT-001',
  appVersion: '1.0.0',
  environment: 'testing',
  folderUrl: 'PASTE_GOOGLE_DRIVE_FOLDER_URL',
  spreadsheetUrl: 'PASTE_SPREADSHEET_URL'
};
const TRADEFLOW_SENTRY_DEFAULT_DSN = 'https://025b261d9f49e6bd8c4ef7408e74f31c@o4510946161524736.ingest.us.sentry.io/4511716397940736';

function getSentryDsn_() {
  return PropertiesService.getScriptProperties().getProperty('SENTRY_DSN') || TRADEFLOW_SENTRY_DEFAULT_DSN;
}

function parseSentryDsn_(dsn) {
  const match = String(dsn || '').match(/^https:\/\/([^@]+)@([^/]+)\/(.+)$/);
  if (!match) return null;
  return { publicKey: match[1], host: match[2], projectId: match[3].replace(/\/$/, ''), dsn: dsn };
}

function getTradeFlowInstallationContext() {
  const scriptId = ScriptApp.getScriptId();
  return Object.assign({}, TRADEFLOW_INSTALLATION, {
    scriptId: scriptId,
    deploymentUrl: ScriptApp.getService().getUrl() || '',
    scriptEditorUrl: 'https://script.google.com/home/projects/' + scriptId + '/edit'
  });
}

function sanitizeSentryValue_(value, depth) {
  const blocked = /password|pin|token|secret|authorization|cookie|appstate|customer|client|rows|payload/i;
  if (depth > 2) return '[Truncated]';
  if (value === null || value === undefined) return value;
  if (value instanceof Error) return { name: value.name, message: value.message, stack: value.stack };
  if (Array.isArray(value)) return value.slice(0, 10).map(item => sanitizeSentryValue_(item, depth + 1));
  if (typeof value === 'object') {
    const out = {};
    Object.keys(value).slice(0, 20).forEach(key => {
      out[key] = blocked.test(key) ? '[Filtered]' : sanitizeSentryValue_(value[key], depth + 1);
    });
    return out;
  }
  if (typeof value === 'string') return value.length > 500 ? value.slice(0, 500) + '...' : value;
  return value;
}

function buildSentryEvent_(error, context) {
  const install = getTradeFlowInstallationContext();
  const err = error instanceof Error ? error : new Error(String(error || 'Unknown Apps Script error'));
  const ctx = context || {};
  return {
    event_id: Utilities.getUuid().replace(/-/g, ''),
    timestamp: new Date().toISOString(),
    platform: 'javascript',
    logger: 'google-apps-script',
    environment: install.environment,
    release: 'tradeflow@' + install.appVersion,
    message: err.message,
    exception: { values: [{ type: err.name || 'Error', value: err.message, stacktrace: { frames: String(err.stack || '').split('\n').slice(1, 30).map(line => ({ function: line.trim() })) } }] },
    tags: {
      product: install.product,
      edition: install.edition,
      client_id: install.clientId,
      installation_id: install.installationId,
      environment: install.environment,
      release: 'tradeflow@' + install.appVersion,
      module: ctx.module || 'backend',
      function_name: ctx.functionName || 'unknown'
    },
    extra: sanitizeSentryValue_(Object.assign({}, ctx, { installation: install, action: ctx.action || '' }), 0)
  };
}

function reportTradeFlowError_(error, context) {
  try {
    const dsn = getSentryDsn_();
    const parsed = parseSentryDsn_(dsn);
    if (!parsed) return console.error('Sentry DSN is missing or invalid');
    const event = buildSentryEvent_(error, context);
    const envelope = [JSON.stringify({ dsn: dsn, sent_at: new Date().toISOString() }), JSON.stringify({ type: 'event' }), JSON.stringify(event)].join('\n');
    UrlFetchApp.fetch('https://' + parsed.host + '/api/' + parsed.projectId + '/envelope/', {
      method: 'post',
      contentType: 'application/x-sentry-envelope',
      payload: envelope,
      muteHttpExceptions: true
    });
  } catch (reportingError) {
    console.error('Sentry reporting failed', reportingError);
  }
}

function withSentryReporting_(functionName, callback, context) {
  try {
    return callback();
  } catch (error) {
    if (!error || !error._tradeFlowSentryReported) {
      reportTradeFlowError_(error, Object.assign({ functionName: functionName }, context || {}));
      try {
        if (error && typeof error === 'object') error._tradeFlowSentryReported = true;
      } catch (markerError) {}
    }
    throw error;
  }
}

function testSentryConnection() {
  try {
    throw new Error('TradeFlow backend Sentry test ' + new Date().toISOString());
  } catch (error) {
    reportTradeFlowError_(error, { functionName: 'testSentryConnection', module: 'sentry', action: 'manual_test' });
    return { ok: true, message: 'Sentry test event submitted. Confirm it in Sentry.' };
  }
}

function doGet(e) {
  const asset = e && e.parameter && e.parameter.asset;
  const view = e && e.parameter && e.parameter.view;
  if (asset === "manifest") return _tradeFlowPwaManifest_();
  if (asset === "sw") return _tradeFlowServiceWorker_();
  if (asset === "icon") return _tradeFlowIconSvg_();
  if (view === "capture") {
    var captureOutput = HtmlService.createHtmlOutputFromFile('CaptureRuntime')
      .setTitle('NDS Capture Runtime')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
    captureOutput.addMetaTag('viewport', 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes');
    return captureOutput;
  }

  var output = HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('TradeFlow Pro')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  
  output.addMetaTag('viewport', 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes');
  return output;
}

function getCaptureRuntimeUrl() {
  return CAPTURE_RUNTIME_URL;
}

function _tradeFlowPwaManifest_() {
  const manifest = {
    name: "TradeFlow Pro",
    short_name: "TradeFlow",
    description: "Complete inventory management system",
    start_url: "./",
    scope: "./",
    display: "standalone",
    display_override: ["window-controls-overlay", "standalone", "minimal-ui", "browser"],
    background_color: "#071a33",
    theme_color: "#f2d16b",
    orientation: "any",
    categories: ["business", "productivity", "finance"],
    icons: [
      { src: "?asset=icon", sizes: "192x192", type: "image/svg+xml", purpose: "any maskable" },
      { src: "?asset=icon", sizes: "512x512", type: "image/svg+xml", purpose: "any maskable" }
    ]
  };
  return ContentService
    .createTextOutput(JSON.stringify(manifest))
    .setMimeType(ContentService.MimeType.JSON);
}

function _tradeFlowIconSvg_() {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="112" fill="#071a33"/><path d="M80 128h352v256H80z" fill="#0b2345"/><path d="M104 154h304v36H104zM104 322h304v36H104z" fill="#f2d16b"/><circle cx="162" cy="256" r="54" fill="#3ec18e"/><path d="M242 205h96c41 0 74 33 74 74s-33 74-74 74h-96V205zm54 50v48h42a24 24 0 0 0 0-48h-42z" fill="#fff"/></svg>';
  return ContentService
    .createTextOutput(svg)
    .setMimeType(ContentService.MimeType.TEXT);
}

function _tradeFlowServiceWorker_() {
  const js = [
    "const TRADEFLOW_CACHE = 'tradeflow-pro-v3-shell-v1';",
    "const SHELL_ASSETS = ['./', '?asset=manifest', '?asset=icon'];",
    "self.addEventListener('install', event => {",
    "  event.waitUntil(caches.open(TRADEFLOW_CACHE).then(cache => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting()));",
    "});",
    "self.addEventListener('activate', event => {",
    "  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== TRADEFLOW_CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));",
    "});",
    "self.addEventListener('fetch', event => {",
    "  const req = event.request;",
    "  if (req.method !== 'GET') return;",
    "  if (req.mode === 'navigate') {",
    "    event.respondWith(fetch(req).then(res => {",
    "      const copy = res.clone(); caches.open(TRADEFLOW_CACHE).then(cache => cache.put('./', copy)); return res;",
    "    }).catch(() => caches.match('./')));",
    "    return;",
    "  }",
    "  event.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {",
    "    if (res && res.ok) caches.open(TRADEFLOW_CACHE).then(cache => cache.put(req, res.clone()));",
    "    return res;",
    "  }).catch(() => hit)));",
    "});"
  ].join("\n");
  return ContentService
    .createTextOutput(js)
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}

// ============================================================
// 2. UTILITIES
// ============================================================

function _safeLastRow(sheet, headerRow) {
  const lr = sheet.getLastRow();
  return Math.max(lr, headerRow || 1);
}

function _toDateOnly(value) {
  if (!value) return null;
  const date = value instanceof Date ? new Date(value) : new Date(value);
  if (isNaN(date.getTime())) return null;
  date.setHours(0, 0, 0, 0);
  return date;
}

function _formatDate(date) {
  if (!date) return "";
  const d = date instanceof Date ? date : new Date(date);
  if (isNaN(d.getTime())) return "";
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return yyyy + '-' + mm + '-' + dd;
}

function _formatDateTime(date) {
  if (!date) return "";
  const d = date instanceof Date ? date : new Date(date);
  if (isNaN(d.getTime())) return "";
  return Utilities.formatDate(d, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
}

function _serializeDate(value) {
  if (!value) return "";
  try {
    const d = value instanceof Date ? value : new Date(value);
    if (isNaN(d.getTime())) return "";
    return Utilities.formatDate(d, Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ss");
  } catch (e) {
    return "";
  }
}

function _isTruthy(value) {
  const s = (value || "").toString().trim().toLowerCase();
  return value === true || s === "true" || s === "yes" || s === "y" || s === "1";
}

function _normalizeString(value) {
  return (value || "").toString().trim();
}

function _parseJson(value) {
  if (!value) return null;
  try {
    return typeof value === 'object' ? value : JSON.parse(value);
  } catch (e) {
    return null;
  }
}

function _stringifyJson(obj) {
  try {
    return JSON.stringify(obj || {});
  } catch (e) {
    return "";
  }
}

function _bytesToHex(bytes) {
  return bytes.map(function(byte) {
    const value = byte < 0 ? byte + 256 : byte;
    return ("0" + value.toString(16)).slice(-2);
  }).join("");
}

function _generateId(prefix, existingIds) {
  let maxNum = 0;
  const regex = new RegExp('^' + prefix + '(\\d+)$', 'i');
  (existingIds || []).forEach(function(id) {
    const m = String(id || '').match(regex);
    if (m) {
      const n = parseInt(m[1], 10);
      if (!isNaN(n) && n > maxNum) maxNum = n;
    }
  });
  return prefix + String(maxNum + 1).padStart(3, '0');
}

// ============================================================
// 3. CACHE MANAGEMENT
// ============================================================

var EP_CACHE_TTL_STOCK_SEC = 90;
var EP_CACHE_TTL_CATEGORIES_SEC = 600;
var EP_CACHE_TTL_STAFF_SEC = 300;
var EP_CACHE_TTL_SETTINGS_SEC = 600;
var EP_CACHE_TTL_DASHBOARD_SEC = 45;
var EP_CACHE_TTL_PRODUCTS_SEC = 120;

function _cacheKey(suffix) {
  return 'ep_' + String(suffix || '');
}

function _cacheGetJson(key) {
  try {
    const raw = CacheService.getScriptCache().get(String(key));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function _cachePutJson(key, obj, ttlSec) {
  try {
    CacheService.getScriptCache().put(String(key), JSON.stringify(obj), Number(ttlSec) || 300);
  } catch (e) {}
}

function _cacheRemove(key) {
  try {
    CacheService.getScriptCache().remove(String(key));
  } catch (e) {}
}

function _cacheBustAll() {
  try {
    const cache = CacheService.getScriptCache();
    cache.remove(_cacheKey('stock_map'));
    cache.remove(_cacheKey('categories'));
    cache.remove(_cacheKey('staff_list'));
    cache.remove(_cacheKey('app_settings'));
    cache.remove(_cacheKey('products_index'));
    cache.remove(_cacheKey('dash_ver'));
    cache.remove(_cacheKey('metrics_today'));
  } catch (e) {}
}

// ============================================================
// 4. SHEET DEFINITIONS
// ============================================================

var EP_SHEET_DEFS = {
  ProductCategoryConfig: ["Category ID", "Category Name"],
  ProductMaster: [
    "Product ID", "Product Name", "Category ID", "Brand", "Supplier", "Barcode",
    "Unit Measure", "Unit Price", "Current Stock", "Reorder Level", "Batch Number",
    "Expiry Date", "Storage Condition", "Size Variant", "Created At",
    "Batch Handled", "Batch Measure", "Units per Batch", "Batch Price"
  ],
  RestockProductLog: [
    "Date Restocked", "Product ID", "Product Name", "Category ID", "Qty Added",
    "Batch Number", "Expiry Date", "Staff ID"
  ],
  InventoryLedger: [
    "Restock Date", "Product ID", "Product", "Batch ID", "Restock Event ID",
    "Quantity Received", "Quantity Remaining", "Unit Cost", "Selling Price Snapshot",
    "Total Cost", "Expected Revenue", "Expected Margin", "Realized Margin",
    "Remaining Margin", "Status"
  ],
  StaffTabAccess: ["Tab ID", "Can View", "Can Edit", "Updated At"],
  AutomatedExpenses: ["ID", "Category", "Expense", "Amount", "Frequency", "Start Date", "Active", "Notes", "Created At"],
  SalesLog: [
    "Sale ID", "Date of Sale", "Product ID", "Product Name", "Category ID", "Unit of Measure",
    "Qty", "Unit Price", "Gross", "Staff ID", "Status", "Notes",
    "Client Name", "Client Phone"
  ],
  StaffMaster: ["Staff ID", "Full Name", "Role", "Phone Number", "Email", "Status"],
  DailyLedger: [
    "Date", "Total Sales", "Discounts", "Net Sales", "Cash In", "Cash Out",
    "Top Product", "Category Breakdown", "Staff Totals"
  ],
  WeeklyLedger: [
    "Week Number", "Start Date", "End Date", "Total Sales", "Net Sales", "Discounts",
    "Category Mix", "Top 5 Products", "Restock vs Sales", "Staff Performance"
  ],
  MonthlyLedger: [
    "Month", "Total Sales", "Net Sales", "Discounts", "Category Contribution", "Top 10 Products",
    "Repeat Clients", "Restock Frequency", "Staff Leaderboard", "Profit Snapshot"
  ],
  Settings: ["Key", "Value", "Updated At"],
  SafeConfig: ["Date Changed", "Portal", "User Name", "Password"],
  AppState: ["Key", "Value", "Updated At"]
};

var EP_PRODUCT_MASTER_WIDTH = 19;
var EP_SALES_LOG_WIDTH = 14;

// ============================================================
// 5. SHEET HELPERS
// ============================================================

function _ensureSheet(ss, sheetName, headers) {
  let sheet = ss.getSheetByName(sheetName);
  let created = false;
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
    created = true;
  }
  if (headers && headers.length) {
    const existing = sheet.getRange(1, 1, 1, Math.max(headers.length, sheet.getLastColumn())).getValues()[0] || [];
    const needsUpdate = headers.some(function(h, i) {
      return (existing[i] || "").toString().trim() !== h;
    });
    if (needsUpdate || sheet.getLastRow() < 1) {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      try { sheet.setFrozenRows(1); } catch (e) {}
      try { sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold"); } catch (e) {}
    }
  }
  return { sheet: sheet, created: created };
}

function _ensureAllSheets(ss) {
  const results = {};
  Object.keys(EP_SHEET_DEFS).forEach(function(name) {
    const result = _ensureSheet(ss, name, EP_SHEET_DEFS[name]);
    results[name] = result.created;
  });
  return results;
}

function _getSheetData(sheet, startRow, numRows, numCols) {
  if (!sheet) return [];
  const lr = _safeLastRow(sheet, 1);
  if (lr < (startRow || 2)) return [];
  const rows = numRows || (lr - (startRow || 2) + 1);
  if (rows <= 0) return [];
  const cols = numCols || sheet.getLastColumn();
  return sheet.getRange(startRow || 2, 1, rows, cols).getValues();
}

function _appendRow(sheet, values) {
  if (!sheet) return;
  sheet.appendRow(values);
}

function _updateCell(sheet, row, col, value) {
  if (!sheet || row < 1 || col < 1) return;
  sheet.getRange(row, col).setValue(value);
}

// ============================================================
// 6. PRODUCT MASTER
// ============================================================

function _getProductMasterData(ss) {
  const sheet = ss.getSheetByName('ProductMaster');
  if (!sheet) return [];
  return _getSheetData(sheet, 2, null, EP_PRODUCT_MASTER_WIDTH);
}

function _parseProductRow(row, rowIndex) {
  const productId = _normalizeString(row[0]);
  if (!productId) return null;
  return {
    rowIndex: rowIndex,
    productId: productId,
    productName: _normalizeString(row[1]),
    categoryId: _normalizeString(row[2]),
    staffId: _normalizeString(row[3]),
    supplier: _normalizeString(row[4]),
    barcode: _normalizeString(row[5]),
    unitMeasure: _normalizeString(row[6]),
    unitPrice: row[7] === "" ? null : Number(row[7]),
    unitCost: row[8] === "" ? null : Number(row[8]),
    reorderLevel: row[9] === "" ? null : Number(row[9]),
    batchNumber: _normalizeString(row[10]),
    expiryDate: _toDateOnly(row[11]),
    storageCondition: _normalizeString(row[12]),
    sizeVariant: _normalizeString(row[13]),
    createdAt: row[14],
    batchHandled: _isTruthy(row[15]),
    batchMeasure: _normalizeString(row[16]),
    batchUnits: row[17] === "" ? null : Number(row[17]),
    batchPrice: row[18] === "" ? null : Number(row[18])
  };
}

function _buildProductIndex(ss) {
  const cacheKey = _cacheKey('products_index');
  const cached = _cacheGetJson(cacheKey);
  if (cached) return cached;

  const data = _getProductMasterData(ss);
  const byId = {};
  const byCategory = {};
  const byBarcode = {};

  data.forEach(function(row, i) {
    const parsed = _parseProductRow(row, i + 2);
    if (!parsed) return;
    byId[parsed.productId] = parsed;
    if (parsed.categoryId) {
      if (!byCategory[parsed.categoryId]) byCategory[parsed.categoryId] = [];
      byCategory[parsed.categoryId].push(parsed);
    }
    if (parsed.barcode) {
      byBarcode[parsed.barcode] = parsed;
    }
  });

  const result = { byId: byId, byCategory: byCategory, byBarcode: byBarcode };
  _cachePutJson(cacheKey, result, EP_CACHE_TTL_PRODUCTS_SEC);
  return result;
}

function _buildStockMap(ss) {
  const cacheKey = _cacheKey('stock_map');
  const cached = _cacheGetJson(cacheKey);
  if (cached) return cached;

  const map = {};
  
  // Restock additions
  const restockSheet = ss.getSheetByName('RestockProductLog');
  if (restockSheet) {
    const data = _getSheetData(restockSheet, 2, null, 8);
    data.forEach(function(row) {
      const pid = _normalizeString(row[1]);
      if (!pid) return;
      const qty = Number(row[4]) || 0;
      map[pid] = (map[pid] || 0) + qty;
    });
  }

  // Sales deductions
  const salesSheet = ss.getSheetByName('SalesLog');
  if (salesSheet) {
    const data = _getSheetData(salesSheet, 2, null, EP_SALES_LOG_WIDTH);
    data.forEach(function(row) {
      const status = _normalizeString(row[10]);
      // Only deduct Paid and Pending (cart holds)
      if (status !== 'Paid' && status !== 'Pending') return;
      const pid = _normalizeString(row[2]);
      if (!pid) return;
      const qty = Number(row[6]) || 0;
      map[pid] = (map[pid] || 0) - qty;
    });
  }

  // Stock adjustments (negative)
  const adjSheet = ss.getSheetByName('StockAdjustments');
  if (adjSheet) {
    const data = _getSheetData(adjSheet, 2, null, 8);
    data.forEach(function(row) {
      const pid = _normalizeString(row[1]);
      if (!pid) return;
      const qty = Number(row[3]) || 0;
      map[pid] = (map[pid] || 0) - qty;
    });
  }

  _cachePutJson(cacheKey, map, EP_CACHE_TTL_STOCK_SEC);
  return map;
}

function getProductStock(productId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const map = _buildStockMap(ss);
  return map[productId] || 0;
}

function getProductById(productId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const index = _buildProductIndex(ss);
  return index.byId[productId] || null;
}

function getProductsByCategory(categoryId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const index = _buildProductIndex(ss);
  return index.byCategory[categoryId] || [];
}

function getProductsList() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const index = _buildProductIndex(ss);
  return Object.values(index.byId);
}

function getProductByBarcode(barcode) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const index = _buildProductIndex(ss);
  return index.byBarcode[barcode] || null;
}

// ============================================================
// 7. APP STATE PERSISTENCE
// ============================================================

function getAppState() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('AppState');
  if (!sheet) {
    _ensureSheet(ss, 'AppState', ['Key', 'Value', 'Updated At']);
    return _getDefaultState();
  }
  
  const data = _getSheetData(sheet, 2, null, 2);
  const values = {};
  data.forEach(function(row) {
    const key = _normalizeString(row[0]);
    if (!key) return;
    values[key] = row[1] == null ? '' : String(row[1]);
  });

  Object.keys(values).forEach(function(key) {
    if (!key.endsWith(APP_STATE_CHUNK_COUNT_SUFFIX)) return;
    const baseKey = key.slice(0, -APP_STATE_CHUNK_COUNT_SUFFIX.length);
    const count = Number(values[key] || 0);
    if (!baseKey || count <= 0) return;
    let combined = '';
    for (let i = 0; i < count; i++) {
      combined += values[baseKey + APP_STATE_CHUNK_SUFFIX + i] || '';
    }
    values[baseKey] = combined;
  });

  const state = {};
  Object.keys(values).forEach(function(key) {
    if (key.endsWith(APP_STATE_CHUNK_COUNT_SUFFIX) || key.indexOf(APP_STATE_CHUNK_SUFFIX) !== -1) return;
    const value = values[key];
    try {
      state[key] = JSON.parse(value);
    } catch (e) {
      state[key] = value;
    }
  });
  
  // Merge with defaults
  const defaults = _getDefaultState();
  Object.keys(defaults).forEach(function(key) {
    if (!(key in state)) {
      state[key] = defaults[key];
    }
  });
  
  return state;
}

function saveAppState(payload) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('AppState');
  if (!sheet) {
    sheet = _ensureSheet(ss, 'AppState', ['Key', 'Value', 'Updated At']).sheet;
  }
  
  const now = new Date();
  const nowIso = now.toISOString();
  payload = payload || {};
  payload._meta = Object.assign({}, payload._meta || {}, {
    serverUpdatedAt: nowIso,
    savedAt: nowIso
  });

  const rows = [];
  Object.keys(payload).forEach(function(key) {
    const value = JSON.stringify(payload[key]);
    if (value.length <= APP_STATE_CHUNK_SIZE) {
      rows.push([key, value, now]);
    } else {
      const chunkCount = Math.ceil(value.length / APP_STATE_CHUNK_SIZE);
      rows.push([key + APP_STATE_CHUNK_COUNT_SUFFIX, String(chunkCount), now]);
      for (let i = 0; i < chunkCount; i++) {
        rows.push([
          key + APP_STATE_CHUNK_SUFFIX + i,
          value.slice(i * APP_STATE_CHUNK_SIZE, (i + 1) * APP_STATE_CHUNK_SIZE),
          now
        ]);
      }
    }
  });

  sheet.clearContents();
  sheet.getRange(1, 1, 1, 3).setValues([['Key', 'Value', 'Updated At']]);
  if (rows.length) {
    sheet.getRange(2, 1, rows.length, 3).setValues(rows);
  }
  
  _cacheBustAll();
  return { success: true, savedAt: nowIso, state: payload };
}

function getSyncSnapshot(clientRevision) {
  const state = getAppState();
  state._sync = state._sync || { revision: 0, appliedOps: [] };
  return {
    ok: true,
    state: state,
    serverRevision: Number(state._sync.revision || 0),
    serverUpdatedAt: (state._meta && state._meta.serverUpdatedAt) || '',
    clientRevision: Number(clientRevision || 0)
  };
}

function pushSyncOps(ops, clientRevision, deviceId) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    let state = getAppState();
    state._sync = state._sync || { revision: 0, appliedOps: [] };
    const applied = {};
    (state._sync.appliedOps || []).forEach(function(opId) { applied[String(opId)] = true; });
    (Array.isArray(ops) ? ops : []).forEach(function(op) {
      const opId = String((op && op.opId) || '');
      if (!opId || applied[opId]) return;
      state = mergeStateRecords_(state, (op && (op.payload || op.state)) || {});
      applied[opId] = true;
      state._sync.revision = Number(state._sync.revision || 0) + 1;
    });
    state._sync.deviceId = String(deviceId || state._sync.deviceId || '');
    state._sync.appliedOps = Object.keys(applied).slice(-500);
    state._sync.lastSyncAt = new Date().toISOString();
    const result = saveAppState(state);
    return {
      ok: true,
      state: result.state || state,
      serverRevision: Number(state._sync.revision || 0),
      appliedOps: state._sync.appliedOps,
      clientRevision: Number(clientRevision || 0),
      deviceId: String(deviceId || '')
    };
  } finally {
    lock.releaseLock();
  }
}

function getSyncStatus(deviceId) {
  const state = getAppState();
  const sync = state._sync || {};
  return {
    ok: true,
    deviceId: String(deviceId || ''),
    serverRevision: Number(sync.revision || 0),
    serverUpdatedAt: (state._meta && state._meta.serverUpdatedAt) || sync.lastSyncAt || '',
    appliedOps: (sync.appliedOps || []).length
  };
}

function mergeStateRecords_(base, incoming) {
  base = base || {};
  incoming = incoming || {};
  Object.keys(incoming).forEach(function(key) {
    if (key === 'user' || key === 'currentUser' || key === 'currentView') return;
    if (Array.isArray(incoming[key])) {
      base[key] = mergeRowsByIdentity_(base[key] || [], incoming[key], key);
    } else if (incoming[key] && typeof incoming[key] === 'object') {
      base[key] = Object.assign({}, base[key] || {}, incoming[key]);
    } else if (incoming[key] !== undefined) {
      base[key] = incoming[key];
    }
  });
  base.nextId = Math.max(Number(base.nextId || 0), Number(incoming.nextId || 0));
  return base;
}

function mergeRowsByIdentity_(currentRows, incomingRows, entity) {
  const appendOnly = { revenue: true, expenses: true, sales: true, payroll: true, stockEntries: true, stockAdjustments: true, auditLog: true, notifications: true };
  const map = {};
  (Array.isArray(currentRows) ? currentRows : []).forEach(function(row) { map[rowIdentity_(row)] = row; });
  (Array.isArray(incomingRows) ? incomingRows : []).forEach(function(row) {
    const key = rowIdentity_(row);
    if (!map[key] || appendOnly[entity]) {
      map[key] = row;
      return;
    }
    const oldTs = Date.parse(map[key].updatedAt || map[key].timestamp || map[key].createdAt || 0) || 0;
    const newTs = Date.parse(row.updatedAt || row.timestamp || row.createdAt || 0) || 0;
    if (newTs >= oldTs) map[key] = Object.assign({}, map[key], row);
  });
  return Object.keys(map).map(function(key) { return map[key]; });
}

function rowIdentity_(row) {
  row = row || {};
  return String(row.id || row.userId || row.staffId || row.saleId || row.sourceProductId || row.name || JSON.stringify(row));
}

function importAppState(payload) {
  const parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
  return saveAppState(parsed).state;
}

function _getDefaultState() {
  return {
    _meta: {},
    nextId: 1000,
    products: [],
    revenue: [],
    expenses: [],
    restockOrders: [],
    stockEntries: [],
    stockAdjustments: [],
    staffMembers: [],
    settings: {
      allowStaffAddProducts: false,
      allowStaffAddStock: false,
      allowStaffRecordRestocks: false,
      businessType: 'retail_supermarket',
      businessName: 'TradeFlow Pro',
      businessOwnerName: '',
      businessOwnerEmail: '',
      businessWhatsapp: '',
      businessAddress: '',
      requireAdminPortalLogin: false,
      requireStaffPortalLogin: false,
      adminPortalUsername: 'admin',
      setupCompleted: false,
      recurringExpenses: [],
      staffTabAccess: _getDefaultStaffTabAccess()
    },
    notifications: [],
    customUnits: [],
    activeBudget: {
      id: 1001,
      date: _formatDate(new Date()),
      items: [],
      status: 'draft',
      totalBudget: 0
    },
    businessType: 'retail_supermarket',
    businessName: 'TradeFlow Pro',
    businessOwnerName: '',
    businessOwnerEmail: '',
    businessWhatsapp: '',
    businessAddress: ''
  };
}

function _getDefaultStaffTabAccess() {
  const tabIds = [
    'dashboard', 'pos', 'products', 'restock', 'inspection', 'budget', 'ledger',
    'pending', 'stockEntries', 'orders', 'adjustments', 'reports', 'revenue',
    'expenses', 'settings'
  ];
  return tabIds.reduce(function(map, id) {
    map[id] = {
      view: id !== 'settings',
      edit: id !== 'settings'
    };
    return map;
  }, {});
}

function resetAppState() {
  const defaults = _getDefaultState();
  saveAppState(defaults);
  _cacheBustAll();
  return defaults;
}

// ============================================================
// 8. BUSINESS TYPES
// ============================================================

var BUSINESS_TYPES = {
  'retail_supermarket': {
    label: 'Retail Supermarket',
    categories: [
      'Fresh Produce & Vegetables', 'Dairy & Eggs', 'Meat & Poultry',
      'Bakery & Bread', 'Beverages', 'Snacks & Confectionery',
      'Rice, Pasta & Grains', 'Canned & Packaged Foods',
      'Cooking Oil & Spices', 'Frozen Foods', 'Household & Cleaning',
      'Personal Care & Toiletries', 'Baby & Infant Products',
      'Pet Food & Supplies', 'Breakfast Cereals', 'Health & Wellness',
      'Stationery & Office Supplies', 'Cigarettes & Tobacco', 'General Merchandise'
    ]
  },
  'hardware': {
    label: 'Hardware & Building',
    categories: [
      'Cement & Concrete', 'Bricks & Blocks', 'Roofing & Ceiling',
      'Timber & Wood', 'Plumbing & Fittings', 'Electrical & Cables',
      'Paint & Coatings', 'Nails & Fasteners', 'Tiles & Flooring',
      'Glass & Glazing', 'Steel & Metal', 'Garden & Landscaping',
      'Hand Tools & Power Tools', 'Safety Equipment & PPE',
      'Kitchen & Bathroom Fittings', 'Electrical Appliances',
      'Insulation Materials', 'PVC & Plastic Piping'
    ]
  },
  'pharmacy': {
    label: 'Pharmacy & Health',
    categories: [
      'Prescription Medications', 'Over-the-Counter Medicines',
      'Vitamins & Supplements', 'First Aid & Wound Care',
      'Baby & Child Healthcare', 'Personal Hygiene',
      'Beauty & Skincare', 'Oral Care', 'Eye Care',
      'Medical Equipment', 'Health Drinks & Nutrition',
      'Herbal & Traditional Medicines', 'Diabetes & Chronic Care',
      'Pain Relief & Analgesics', 'Allergy & Respiratory',
      'Digestive Health', 'Sexual & Reproductive Health',
      'Pet Medications'
    ]
  },
  'clothing': {
    label: 'Clothing & Fashion',
    categories: [
      "Men's Clothing", "Women's Clothing", "Children's Wear",
      'Footwear', 'Accessories', 'Jewelry & Watches',
      'Traditional Clothing', 'Sportswear', 'Lingerie & Sleepwear',
      'Formal Wear', 'Denim & Jeans', 'Outerwear',
      'Swimwear', 'School Uniforms', 'Workwear & Corporate',
      'Hosiery & Socks', 'Belts & Leather Goods', 'Hats & Caps'
    ]
  },
  'electronics': {
    label: 'Electronics & Appliances',
    categories: [
      'Smartphones & Tablets', 'Laptops & Computers',
      'Televisions & Home Entertainment', 'Audio & Sound Systems',
      'Kitchen Appliances', 'Refrigerators & Freezers',
      'Washing Machines & Dryers', 'Mobile Accessories',
      'Camera & Photography', 'Gaming & Video Games',
      'Computer Accessories', 'Air Conditioners & Fans',
      'Smart Home Devices', 'Vacuum Cleaners', 'Electric Tools',
      'Fitness & Health Tech', 'Batteries & Power Banks',
      'Cables & Connectivity'
    ]
  },
  'furniture': {
    label: 'Furniture Store',
    categories: [
      'Living Room Furniture', 'Bedroom Furniture',
      'Dining Room Furniture', 'Office Furniture',
      'Outdoor Furniture', 'Kitchen Cabinets',
      'Mattresses & Bedding', 'Curtains & Blinds',
      'Rugs & Carpets', 'Lighting Fixtures',
      'Shelving & Storage', 'TV Stands & Entertainment Units',
      "Children's Furniture", 'Bathroom Furniture',
      'Doors & Door Fittings', 'Decorative Items & Mirrors',
      'Window Frames & Glass', 'Custom Furniture Orders'
    ]
  },
  'automotive': {
    label: 'Automotive Parts',
    categories: [
      'Engine Parts', 'Brake Systems', 'Transmission & Gearbox',
      'Suspension & Steering', 'Electrical & Ignition',
      'Tires & Wheels', 'Batteries & Charging',
      'Filters', 'Exhaust Systems', 'Air Conditioning Parts',
      'Body Parts & Panels', 'Lighting & Bulbs',
      'Wipers & Windows', 'Cooling System',
      'Lubricants & Oils', 'Car Accessories',
      'Tools & Garage Equipment', 'Performance Upgrades'
    ]
  },
  'restaurant': {
    label: 'Restaurant & Food',
    categories: [
      'Beverages', 'Main Dishes', 'Sides & Accompaniments',
      'Desserts & Pastries', 'Breakfast Items', 'Lunch Specials',
      'Dinner Specials', 'Salads & Healthy Options',
      'Sandwiches & Wraps', 'Pasta & Noodle Dishes',
      'Pizza & Italian', 'Traditional Zambian Dishes',
      'International Cuisine', 'Catering & Events',
      "Kid's Meals", 'Seafood & Fish',
      'Vegetarian & Vegan', 'Alcoholic & Non-alcoholic'
    ]
  },
  'cosmetics': {
    label: 'Cosmetics & Beauty',
    categories: [
      'Haircare', 'Skincare', 'Makeup',
      'Nail Care', 'Fragrances & Perfumes',
      'Salon Equipment & Tools', 'Hair Extensions & Wigs',
      "Men's Grooming", 'Sun Protection',
      'Bath & Body', 'Organic & Natural Products',
      'Anti-aging & Skincare', 'Professional Makeup',
      'Beauty Accessories', 'Eyelashes & Brows',
      'Tattoo & Permanent Makeup', 'Spa & Wellness Products',
      'Hair Dyes & Color'
    ]
  },
  'agriculture': {
    label: 'Agricultural Supplies',
    categories: [
      'Fertilizers', 'Seeds', 'Pesticides & Herbicides',
      'Farming Tools & Equipment', 'Animal Feed & Supplements',
      'Veterinary Supplies', 'Irrigation Equipment',
      'Greenhouses & Shade Nets', 'Harvesting Tools',
      'Livestock Equipment', 'Packaging & Storage',
      'Soil Testing & Analysis', 'Drainage & Water Management',
      'Organic Farming Supplies', 'Horticulture & Flowers',
      'Poultry Equipment', 'Beekeeping Equipment',
      'Fish Farming Supplies'
    ]
  },
  'stationery': {
    label: 'Stationery & Office',
    categories: [
      'Paper & Printing', 'Writing Instruments',
      'Office Furniture', 'Filing & Organization',
      'Computer Supplies', 'School Supplies',
      'Art & Craft Materials', 'Office Machines',
      'Envelopes & Mailing', 'Business Forms',
      'Whiteboards & Presentation', 'Packaging',
      'Cleaning Supplies', 'Safety & First Aid',
      'Technology Accessories', 'Breakroom Supplies',
      'Desk Accessories', 'Office Decor & Plants'
    ]
  },
  'cellular': {
    label: 'Cellular & Airtime',
    categories: [
      'Mobile Airtime', 'Mobile Money Transactions',
      'Data Bundles', 'Smartphones & Tablets',
      'SIM Cards', 'Mobile Accessories',
      'Bill Payments', 'Prepaid Electricity',
      'Digital Money Transfers', 'International Calling',
      'Television Subscriptions', 'Internet Services',
      'Digital Gift Cards', 'Mobile Banking Services',
      'Insurance Products', 'Travel & Ticket Services',
      'Education & School Fees', 'Donations & Zakat'
    ]
  },
  'construction': {
    label: 'Construction & Building',
    categories: [
      'Materials', 'Lumber', 'Concrete & Cement',
      'Steel & Metal', 'Roofing & Ceiling',
      'Plumbing & Pipes', 'Electrical & Wiring',
      'Painting & Finishing', 'Flooring & Tiling',
      'Windows & Glass', 'Construction Tools',
      'Safety Gear & PPE', 'Landscaping & Exterior',
      'HVAC', 'Insulation & Soundproofing',
      'Scaffolding & Ladders', 'Formwork & Shuttering',
      'Waterproofing & Treatments'
    ]
  },
  'pet_supplies': {
    label: 'Pet Supplies',
    categories: [
      'Pet Food', 'Pet Accessories',
      'Bedding & Kennels', 'Grooming Products',
      'Pet Medications', 'Toys & Entertainment',
      'Pet Travel & Carriers', 'Fish Tanks & Aquarium',
      'Bird Cages & Supplies', 'Reptile & Terrarium',
      'Training Aids', 'Hygiene & Waste Management',
      'Feeding Bowls & Waterers', 'Veterinary Equipment',
      'Pet Insurance', 'Dog Clothing & Accessories',
      'Cat Furniture', 'Pet ID & Tracking'
    ]
  },
  'bookstore': {
    label: 'Bookstore & Learning',
    categories: [
      'School Textbooks', 'University & College Texts',
      "Children's Books & Readers", 'Fiction & Novels',
      'Non-Fiction', 'Educational Software',
      'Art & Craft Supplies', 'Musical Instruments',
      'Stationery', 'Educational Toys & Games',
      'Curriculum Materials', 'E-books & Digital Libraries',
      'Language Learning', 'Reference Materials',
      'Scientific Equipment', 'Study Guides & Exam Prep',
      'Religious & Spiritual Books', 'Career & Vocational Guides'
    ]
  }
};

function getBusinessTypes() {
  return BUSINESS_TYPES;
}

function getBusinessTypeCategories(businessType) {
  return BUSINESS_TYPES[businessType]?.categories || [];
}

// ============================================================
// 9. CATEGORIES
// ============================================================

function _ensureCategory(ss, categoryName) {
  const sheet = ss.getSheetByName('ProductCategoryConfig');
  if (!sheet) return null;
  
  const data = _getSheetData(sheet, 2, null, 2);
  const nameLower = categoryName.toLowerCase();
  
  for (let i = 0; i < data.length; i++) {
    const id = _normalizeString(data[i][0]);
    const name = _normalizeString(data[i][1]);
    if (name.toLowerCase() === nameLower) {
      return { categoryId: id, categoryName: name };
    }
  }
  
  // Create new category
  const existingIds = data.map(function(row) { return _normalizeString(row[0]); });
  const newId = _generateId('CAT', existingIds);
  sheet.appendRow([newId, categoryName]);
  _cacheRemove(_cacheKey('categories'));
  return { categoryId: newId, categoryName: categoryName, created: true };
}

function getCategories() {
  const cacheKey = _cacheKey('categories');
  const cached = _cacheGetJson(cacheKey);
  if (cached) return cached;
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('ProductCategoryConfig');
  if (!sheet) return [];
  
  const data = _getSheetData(sheet, 2, null, 2);
  const result = data.map(function(row) {
    return {
      id: _normalizeString(row[0]),
      name: _normalizeString(row[1])
    };
  }).filter(function(c) { return c.id; });
  
  _cachePutJson(cacheKey, result, EP_CACHE_TTL_CATEGORIES_SEC);
  return result;
}

function seedCategories(businessType) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const categories = BUSINESS_TYPES[businessType]?.categories || [];
  if (!categories.length) return { added: 0 };
  
  const sheet = ss.getSheetByName('ProductCategoryConfig');
  if (!sheet) return { error: 'Category sheet not found' };
  
  const existing = {};
  const data = _getSheetData(sheet, 2, null, 2);
  data.forEach(function(row) {
    const name = _normalizeString(row[1]);
    if (name) existing[name.toLowerCase()] = true;
  });
  
  let added = 0;
  const existingIds = data.map(function(row) { return _normalizeString(row[0]); });
  let nextId = _generateId('CAT', existingIds);
  
  categories.forEach(function(catName) {
    if (existing[catName.toLowerCase()]) return;
    sheet.appendRow([nextId, catName]);
    nextId = 'CAT' + String(parseInt(nextId.replace('CAT', ''), 10) + 1).padStart(3, '0');
    added++;
  });
  
  _cacheRemove(_cacheKey('categories'));
  return { added: added };
}

// ============================================================
// 10. STAFF
// ============================================================

function getStaffList() {
  const cacheKey = _cacheKey('staff_list');
  const cached = _cacheGetJson(cacheKey);
  if (cached) return cached;
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('StaffMaster');
  if (!sheet) return [];
  
  const data = _getSheetData(sheet, 2, null, 6);
  const result = data.map(function(row) {
    return {
      staffId: _normalizeString(row[0]),
      fullName: _normalizeString(row[1]),
      role: _normalizeString(row[2]),
      phone: _normalizeString(row[3]),
      email: _normalizeString(row[4]),
      status: _normalizeString(row[5]) || 'Active'
    };
  }).filter(function(s) { return s.staffId; });
  
  _cachePutJson(cacheKey, result, EP_CACHE_TTL_STAFF_SEC);
  return result;
}

function addStaffMember(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('StaffMaster');
  if (!sheet) return { error: 'StaffMaster sheet not found' };
  
  const name = _normalizeString(data.fullName);
  const email = _normalizeString(data.email);
  const role = _normalizeString(data.role) || 'Staff';
  const phone = _normalizeString(data.phoneNumber);
  
  if (!name) return { error: 'Full name is required' };
  if (!email) return { error: 'Email is required' };
  
  // Check for duplicate email
  const existing = getStaffList();
  if (existing.some(function(s) { return s.email.toLowerCase() === email.toLowerCase(); })) {
    return { error: 'Email already registered' };
  }
  
  const existingIds = existing.map(function(s) { return s.staffId; });
  const staffId = _generateId('ST', existingIds);
  
  sheet.appendRow([staffId, name, role, phone, email, 'Active']);
  _cacheRemove(_cacheKey('staff_list'));
  
  return { success: true, staffId: staffId, fullName: name };
}

function updateStaffStatus(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('StaffMaster');
  if (!sheet) return { error: 'StaffMaster sheet not found' };
  
  const staffId = _normalizeString(data.staffId);
  const status = _normalizeString(data.status);
  if (!staffId) return { error: 'Staff ID required' };
  if (!status) return { error: 'Status required' };
  
  const rows = _getSheetData(sheet, 2, null, 6);
  for (let i = 0; i < rows.length; i++) {
    if (_normalizeString(rows[i][0]) === staffId) {
      const rowNum = i + 2;
      sheet.getRange(rowNum, 6).setValue(status);
      _cacheRemove(_cacheKey('staff_list'));
      return { success: true, staffId: staffId, status: status };
    }
  }
  
  return { error: 'Staff member not found' };
}

// ============================================================
// 11. SETTINGS
// ============================================================

function getAppSettings() {
  const cacheKey = _cacheKey('app_settings');
  const cached = _cacheGetJson(cacheKey);
  if (cached) return cached;
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Settings');
  if (!sheet) {
    _ensureSheet(ss, 'Settings', ['Key', 'Value', 'Updated At']);
    return { businessName: 'TradeFlow Pro', businessType: 'retail_supermarket', businessOwnerName: '', businessOwnerEmail: '', businessWhatsapp: '', businessAddress: '', setupCompleted: false };
  }
  
  const data = _getSheetData(sheet, 2, null, 2);
  const settings = { businessName: 'TradeFlow Pro', businessType: 'retail_supermarket', businessOwnerName: '', businessOwnerEmail: '', businessWhatsapp: '', businessAddress: '', setupCompleted: false };
  
  data.forEach(function(row) {
    const key = _normalizeString(row[0]);
    const value = row[1];
    if (key === 'BUSINESS_NAME') settings.businessName = value || 'TradeFlow Pro';
    if (key === 'BUSINESS_TYPE') settings.businessType = value || 'retail_supermarket';
    if (key === 'BUSINESS_OWNER_NAME') settings.businessOwnerName = value || '';
    if (key === 'BUSINESS_OWNER_EMAIL') settings.businessOwnerEmail = value || '';
    if (key === 'BUSINESS_WHATSAPP') settings.businessWhatsapp = value || '';
    if (key === 'BUSINESS_ADDRESS') settings.businessAddress = value || '';
    if (key === 'SETUP_COMPLETED') settings.setupCompleted = value === 'true' || value === true;
    if (key === 'SETUP_COMPLETED_AT') settings.setupCompletedAt = value;
  });
  
  _cachePutJson(cacheKey, settings, EP_CACHE_TTL_SETTINGS_SEC);
  return settings;
}

function saveAppSettings(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Settings');
  if (!sheet) {
    sheet = _ensureSheet(ss, 'Settings', ['Key', 'Value', 'Updated At']).sheet;
  }
  
  const now = new Date();
  const keys = {
    'BUSINESS_NAME': data.businessName,
    'BUSINESS_TYPE': data.businessType,
    'BUSINESS_OWNER_NAME': data.businessOwnerName || '',
    'BUSINESS_OWNER_EMAIL': data.businessOwnerEmail || '',
    'BUSINESS_WHATSAPP': data.businessWhatsapp || '',
    'BUSINESS_ADDRESS': data.businessAddress || '',
    'SETUP_COMPLETED': data.setupCompleted ? 'true' : 'false',
    'SETUP_COMPLETED_AT': data.setupCompleted ? now.toISOString() : ''
  };
  
  const existing = {};
  const existingData = _getSheetData(sheet, 2, null, 2);
  existingData.forEach(function(row) {
    const key = _normalizeString(row[0]);
    if (key) existing[key] = true;
  });
  
  Object.keys(keys).forEach(function(key) {
    if (existing[key]) {
      const data = _getSheetData(sheet, 2, null, 2);
      for (let i = 0; i < data.length; i++) {
        if (_normalizeString(data[i][0]) === key) {
          const row = i + 2;
          sheet.getRange(row, 2).setValue(keys[key]);
          sheet.getRange(row, 3).setValue(now);
          return;
        }
      }
    } else {
      sheet.appendRow([key, keys[key], now]);
    }
  });
  
  _cacheRemove(_cacheKey('app_settings'));
  return { success: true };
}

// ============================================================
// 12. SETUP & REPAIR SHEETS
// ============================================================

function setupOrRepairSheets(data) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const businessType = data?.businessType || 'retail_supermarket';
    const businessName = data?.businessName || 'TradeFlow Pro';
    const businessOwnerName = data?.businessOwnerName || '';
    const businessOwnerEmail = data?.businessOwnerEmail || '';
    const businessWhatsapp = data?.businessWhatsapp || '';
    const businessAddress = data?.businessAddress || '';
    
    // Create all sheets
    const results = _ensureAllSheets(ss);
    
    // Seed categories
    const catResult = seedCategories(businessType);
    
    // Save settings
    saveAppSettings({
      businessName: businessName,
      businessType: businessType,
      businessOwnerName: businessOwnerName,
      businessOwnerEmail: businessOwnerEmail,
      businessWhatsapp: businessWhatsapp,
      businessAddress: businessAddress,
      setupCompleted: true,
      setupCompletedAt: new Date().toISOString()
    });
    
    // Ensure SafeConfig exists
    _ensureSafeConfigSheet(ss);
    
    _cacheBustAll();
    
    return {
      success: true,
      message: 'Sheets ready: ' + Object.keys(results).filter(function(k) { return results[k]; }).join(', '),
      sheetsCreated: Object.keys(results).filter(function(k) { return results[k]; }),
      categoriesAdded: catResult.added || 0
    };
  } catch (e) {
    return { error: true, message: e.message || 'Setup failed' };
  }
}

function _ensureSafeConfigSheet(ss) {
  const result = _ensureSheet(ss, 'SafeConfig', ['Date Changed', 'Portal', 'User Name', 'Password']);
  const sheet = result.sheet;
  
  // Seed default portals
  const portals = ['staff', 'admin'];
  const existing = {};
  const data = _getSheetData(sheet, 2, null, 2);
  data.forEach(function(row) {
    const portal = _normalizeString(row[1]);
    if (portal) existing[portal] = true;
  });
  
  portals.forEach(function(portal) {
    if (!existing[portal]) {
      sheet.appendRow([new Date(), portal, '', 'NOT_SET']);
    }
  });
  
  // Hide password column
  try { sheet.hideColumns(4); } catch (e) {}
  
  return sheet;
}

// ============================================================
// 13. AUTHENTICATION
// ============================================================

var EP_PORTAL_PASSWORD_NOT_SET = "NOT_SET";

function _hashPassword(portal, username, password) {
  const material = portal + ":" + username.toLowerCase() + ":" + password;
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, material, Utilities.Charset.UTF_8);
  return "sha256:" + _bytesToHex(digest);
}

function getPortalAuthStatus(data) {
  const portal = _normalizeString(data?.portal || '');
  if (!portal) return { error: true, message: 'Portal is required' };
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('SafeConfig');
  if (!sheet) return { error: true, message: 'SafeConfig sheet not found' };
  
  const rows = _getSheetData(sheet, 2, null, 4);
  for (let i = 0; i < rows.length; i++) {
    if (_normalizeString(rows[i][1]) === portal) {
      const password = _normalizeString(rows[i][3]);
      return {
        portal: portal,
        passwordRequired: password !== EP_PORTAL_PASSWORD_NOT_SET && password !== '',
        username: _normalizeString(rows[i][2])
      };
    }
  }
  
  return { portal: portal, passwordRequired: false, username: '' };
}

function verifyPortalLogin(data) {
  const portal = _normalizeString(data?.portal || '');
  const username = _normalizeString(data?.username || '');
  const password = data?.password || '';
  
  if (!portal) return { error: true, message: 'Portal is required' };
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('SafeConfig');
  if (!sheet) return { error: true, message: 'SafeConfig sheet not found' };
  
  const rows = _getSheetData(sheet, 2, null, 4);
  for (let i = 0; i < rows.length; i++) {
    if (_normalizeString(rows[i][1]) === portal) {
      const storedPassword = _normalizeString(rows[i][3]);
      const storedUsername = _normalizeString(rows[i][2]);
      
      if (storedPassword === EP_PORTAL_PASSWORD_NOT_SET || storedPassword === '') {
        return { success: true, portal: portal, username: '' };
      }
      
      if (username && password) {
        const hash = _hashPassword(portal, username, password);
        if (hash === storedPassword) {
          return { success: true, portal: portal, username: username };
        }
        // Check plaintext fallback (legacy)
        if (password === storedPassword) {
          sheet.getRange(i + 2, 4).setValue(hash);
          return { success: true, portal: portal, username: username };
        }
      }
      
      return { error: true, message: 'Invalid username or password' };
    }
  }
  
  return { error: true, message: 'Portal not configured' };
}

function updatePortalCredential(data) {
  const portal = _normalizeString(data?.portal || '');
  const username = _normalizeString(data?.username || '');
  const password = data?.password || '';
  const requirePassword = data?.requirePassword === true;
  
  if (!portal) return { error: true, message: 'Portal is required' };
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('SafeConfig');
  if (!sheet) return { error: true, message: 'SafeConfig sheet not found' };
  
  const rows = _getSheetData(sheet, 2, null, 4);
  for (let i = 0; i < rows.length; i++) {
    if (_normalizeString(rows[i][1]) === portal) {
      const rowNum = i + 2;
      const newPassword = requirePassword ? _hashPassword(portal, username, password) : EP_PORTAL_PASSWORD_NOT_SET;
      sheet.getRange(rowNum, 2).setValue(username);
      sheet.getRange(rowNum, 3).setValue(newPassword);
      sheet.getRange(rowNum, 1).setValue(new Date());
      return { success: true, portal: portal, username: username, passwordRequired: requirePassword };
    }
  }
  
  // Create new portal entry
  const newPassword = requirePassword ? _hashPassword(portal, username, password) : EP_PORTAL_PASSWORD_NOT_SET;
  sheet.appendRow([new Date(), portal, username, newPassword]);
  try { sheet.hideColumns(4); } catch (e) {}
  
  return { success: true, portal: portal, username: username, passwordRequired: requirePassword };
}

// ============================================================
// 14. API ENDPOINTS
// ============================================================

// Get all products with stock
function getInventoryData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const products = getProductsList();
  const stockMap = _buildStockMap(ss);
  
  return products.map(function(p) {
    return {
      productId: p.productId,
      productName: p.productName,
      categoryId: p.categoryId,
      unitMeasure: p.unitMeasure,
      unitPrice: p.unitPrice,
      unitCost: p.unitCost,
      stock: stockMap[p.productId] || 0,
      reorderLevel: p.reorderLevel || 0,
      barcode: p.barcode || '',
      expiryDate: p.expiryDate ? _formatDate(p.expiryDate) : '',
      maxStock: 50 // Default, can be enhanced
    };
  });
}

// Record a sale
function recordSale(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('SalesLog');
  if (!sheet) return { error: 'SalesLog sheet not found' };
  
  const productId = _normalizeString(data.productId);
  const qty = Number(data.qty || 0);
  const unitPrice = Number(data.unitPrice || 0);
  const staffId = _normalizeString(data.staffId) || 'SYSTEM';
  const saleId = 'SL' + new Date().toISOString().replace(/\D/g, '').slice(0, 14);
  
  if (!productId) return { error: 'Product ID required' };
  if (qty <= 0) return { error: 'Quantity must be positive' };
  
  const product = getProductById(productId);
  if (!product) return { error: 'Product not found' };
  
  const stock = getProductStock(productId);
  if (stock < qty) return { error: 'Insufficient stock: ' + stock + ' available' };
  
  const gross = qty * (unitPrice || product.unitPrice || 0);
  const now = new Date();
  
  sheet.appendRow([
    saleId, now, productId, product.productName, product.categoryId,
    product.unitMeasure || 'unit', qty, unitPrice || product.unitPrice || 0,
    gross, staffId, 'Paid', '', '', ''
  ]);
  
  _cacheRemove(_cacheKey('stock_map'));
  _cacheRemove(_cacheKey('metrics_today'));
  _cacheRemove(_cacheKey('dash_ver'));
  
  return {
    success: true,
    saleId: saleId,
    productId: productId,
    productName: product.productName,
    qty: qty,
    gross: gross
  };
}

// Record a restock
function recordRestock(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('RestockProductLog');
  if (!sheet) return { error: 'RestockProductLog sheet not found' };
  
  const productId = _normalizeString(data.productId);
  const qty = Number(data.qtyAdded || 0);
  const unitCost = Number(data.unitCost || 0);
  const staffId = _normalizeString(data.staffId) || 'SYSTEM';
  const batchNumber = _normalizeString(data.batchNumber) || ('B' + new Date().toISOString().replace(/\D/g, '').slice(0, 10));
  
  if (!productId) return { error: 'Product ID required' };
  if (qty <= 0) return { error: 'Quantity must be positive' };
  
  const product = getProductById(productId);
  if (!product) return { error: 'Product not found' };
  
  const now = new Date();
  sheet.appendRow([
    now, productId, product.productName, product.categoryId,
    qty, batchNumber, data.expiryDate || '', staffId
  ]);
  
  _cacheRemove(_cacheKey('stock_map'));
  _cacheRemove(_cacheKey('dash_ver'));
  
  return {
    success: true,
    productId: productId,
    productName: product.productName,
    qtyAdded: qty,
    batchNumber: batchNumber
  };
}

// ============================================================
// 15. EXPORT FUNCTIONS
// ============================================================

function exportReportTablesToSheets(bundle) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    
    // Create report sheet
    const reportSheet = ss.getSheetByName('ReportExport');
    if (reportSheet) {
      ss.deleteSheet(reportSheet);
    }
    const newSheet = ss.insertSheet('ReportExport');
    
    // Write KPI summary
    const kpis = bundle.kpis || {};
    newSheet.getRange(1, 1).setValue('KPI Report');
    newSheet.getRange(2, 1).setValue('Total Revenue');
    newSheet.getRange(2, 2).setValue(kpis.revenue || 0);
    newSheet.getRange(3, 1).setValue('Gross Margin %');
    newSheet.getRange(3, 2).setValue(kpis.grossMarginPct || 0);
    newSheet.getRange(4, 1).setValue('Net Profit');
    newSheet.getRange(4, 2).setValue(kpis.netProfit || 0);
    newSheet.getRange(5, 1).setValue('COGS');
    newSheet.getRange(5, 2).setValue(kpis.cogs || 0);
    newSheet.getRange(6, 1).setValue('Cash Flow');
    newSheet.getRange(6, 2).setValue(kpis.cashFlow || 0);
    newSheet.getRange(7, 1).setValue('Inventory Value');
    newSheet.getRange(7, 2).setValue(kpis.inventoryValue || 0);
    newSheet.getRange(8, 1).setValue('Expected Profit Remaining');
    newSheet.getRange(8, 2).setValue(kpis.expectedProfitRemaining || 0);
    newSheet.getRange(9, 1).setValue('Realized Profit');
    newSheet.getRange(9, 2).setValue(kpis.realizedProfit || 0);
    newSheet.getRange(10, 1).setValue('Open Batch Value');
    newSheet.getRange(10, 2).setValue(kpis.openBatchValue || 0);
    newSheet.getRange(11, 1).setValue('Completed Batch Profit');
    newSheet.getRange(11, 2).setValue(kpis.completedBatchProfit || 0);
    newSheet.getRange(12, 1).setValue('Average Margin %');
    newSheet.getRange(12, 2).setValue(kpis.averageMarginPct || 0);
    
    // Restock summary / inventory ledger export
    let row = 15;
    const batchRows = bundle.batchRows || [];
    if (batchRows.length) {
      newSheet.getRange(row, 1).setValue('Restock Summary');
      row++;
      const headers = [
        'Date', 'Product', 'Batch ID', 'Restock Event', 'Qty Received',
        'Qty Remaining', 'Unit Cost', 'Selling Snapshot', 'Total Cost',
        'Expected Revenue', 'Expected Margin', 'Realized Margin',
        'Remaining Margin', 'Status'
      ];
      newSheet.getRange(row, 1, 1, headers.length).setValues([headers]);
      row++;
      batchRows.forEach(function(item) {
        newSheet.getRange(row, 1, 1, headers.length).setValues([[
          item.date || item.restockDate || '',
          item.product || '',
          item.batchId || '',
          item.restockEventId || '',
          Number(item.quantityReceived || 0),
          Number(item.quantityRemaining || 0),
          Number(item.unitCost || 0),
          Number(item.sellingPriceSnapshot || 0),
          Number(item.totalCost || 0),
          Number(item.expectedRevenue || 0),
          Number(item.expectedMargin || 0),
          Number(item.realizedMargin || 0),
          Number(item.remainingMargin || 0),
          item.status || ''
        ]]);
        row++;
      });
    }

    row += 2;
    const productProfitRows = bundle.productProfitRows || [];
    if (productProfitRows.length) {
      newSheet.getRange(row, 1).setValue('Profit by Product');
      row++;
      newSheet.getRange(row, 1, 1, 5).setValues([['Product', 'Stock', 'Inventory Value', 'Realized Margin', 'Remaining Margin']]);
      row++;
      productProfitRows.forEach(function(item) {
        newSheet.getRange(row, 1, 1, 5).setValues([[
          item.product || '',
          Number(item.stock || 0),
          Number(item.inventoryValue || 0),
          Number(item.realizedMargin || 0),
          Number(item.remainingMargin || 0)
        ]]);
        row++;
      });
    }

    // Revenue table
    row += 2;
    const revenueRows = bundle.revenueRows || [];
    if (revenueRows.length) {
      newSheet.getRange(row, 1).setValue('Revenue');
      row++;
      newSheet.getRange(row, 1).setValue('Date');
      newSheet.getRange(row, 2).setValue('Amount');
      newSheet.getRange(row, 3).setValue('Notes');
      row++;
      revenueRows.forEach(function(item) {
        newSheet.getRange(row, 1).setValue(item.date || '');
        newSheet.getRange(row, 2).setValue(item.amount || 0);
        newSheet.getRange(row, 3).setValue(item.notes || '');
        row++;
      });
    }
    
    // Expenses table
    row += 2;
    const expenseRows = bundle.expenseRows || [];
    if (expenseRows.length) {
      newSheet.getRange(row, 1).setValue('Expenses');
      row++;
      newSheet.getRange(row, 1).setValue('Date');
      newSheet.getRange(row, 2).setValue('Category');
      newSheet.getRange(row, 3).setValue('Expense');
      newSheet.getRange(row, 4).setValue('Amount');
      newSheet.getRange(row, 5).setValue('Notes');
      row++;
      expenseRows.forEach(function(item) {
        newSheet.getRange(row, 1).setValue(item.date || '');
        newSheet.getRange(row, 2).setValue(item.category || '');
        newSheet.getRange(row, 3).setValue(item.expenseName || item.name || '');
        newSheet.getRange(row, 4).setValue(item.amount || 0);
        newSheet.getRange(row, 5).setValue(item.notes || '');
        row++;
      });
    }

    row += 2;
    const cogsRows = bundle.cogsRows || [];
    if (cogsRows.length) {
      newSheet.getRange(row, 1).setValue('Stock Adjustments / COGS');
      row++;
      newSheet.getRange(row, 1, 1, 7).setValues([['Date', 'Product', 'Qty', 'COGS', 'Estimated Revenue', 'Estimated Margin', 'Reason']]);
      row++;
      cogsRows.forEach(function(item) {
        newSheet.getRange(row, 1, 1, 7).setValues([[
          item.date || '',
          item.product || '',
          Number(item.qty || 0),
          Number(item.cogs || 0),
          Number(item.estimatedRevenue || 0),
          Number(item.estimatedMargin || 0),
          item.reason || ''
        ]]);
        row++;
      });
    }
    
    // Formatting
    try {
      newSheet.autoResizeColumns(1, 14);
      newSheet.getRange(1, 1, 1, 14).setFontWeight('bold');
    } catch (e) {}
    
    return {
      success: true,
      spreadsheetUrl: ss.getUrl()
    };
  } catch (e) {
    return { error: true, message: e.message || 'Export failed' };
  }
}

// ============================================================
// 16. DASHBOARD METRICS
// ============================================================

function getDashboardMetrics() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const products = getProductsList();
  const stockMap = _buildStockMap(ss);
  
  const totalProducts = products.length;
  const totalStockValue = products.reduce(function(sum, p) {
    const stock = stockMap[p.productId] || 0;
    const cost = p.unitCost || 0;
    return sum + (stock * cost);
  }, 0);
  
  const lowStockItems = products.filter(function(p) {
    const stock = stockMap[p.productId] || 0;
    const reorder = p.reorderLevel || 0;
    return stock <= reorder;
  });
  
  return {
    totalProducts: totalProducts,
    totalStockValue: totalStockValue,
    lowStockCount: lowStockItems.length,
    lowStockItems: lowStockItems.map(function(p) {
      return {
        productId: p.productId,
        productName: p.productName,
        stock: stockMap[p.productId] || 0,
        reorderLevel: p.reorderLevel || 0
      };
    })
  };
}

// ============================================================
// 17. NOTE ON EXPORTS
// ============================================================
// In Google Apps Script, every top-level function is automatically
// callable via google.script.run — no re-exporting needed.
// The _exports wrapper pattern was removed because it caused
// infinite recursion: the wrapper called _exports.fn which
// (due to hoisting) pointed back to the wrapper itself.

var _tfSentry_getProductStock = getProductStock;
getProductStock = function() {
  var args = arguments;
  return withSentryReporting_('getProductStock', function() {
    return _tfSentry_getProductStock.apply(null, args);
  }, { module: 'inventory', action: 'get_product_stock' });
};

var _tfSentry_getProductById = getProductById;
getProductById = function() {
  var args = arguments;
  return withSentryReporting_('getProductById', function() {
    return _tfSentry_getProductById.apply(null, args);
  }, { module: 'inventory', action: 'get_product' });
};

var _tfSentry_getProductsList = getProductsList;
getProductsList = function() {
  var args = arguments;
  return withSentryReporting_('getProductsList', function() {
    return _tfSentry_getProductsList.apply(null, args);
  }, { module: 'inventory', action: 'list_products' });
};

var _tfSentry_getProductByBarcode = getProductByBarcode;
getProductByBarcode = function() {
  var args = arguments;
  return withSentryReporting_('getProductByBarcode', function() {
    return _tfSentry_getProductByBarcode.apply(null, args);
  }, { module: 'scanner', action: 'lookup_barcode' });
};

var _tfSentry_getAppState = getAppState;
getAppState = function() {
  var args = arguments;
  return withSentryReporting_('getAppState', function() {
    return _tfSentry_getAppState.apply(null, args);
  }, { module: 'state', action: 'load' });
};

var _tfSentry_saveAppState = saveAppState;
saveAppState = function() {
  var args = arguments;
  return withSentryReporting_('saveAppState', function() {
    return _tfSentry_saveAppState.apply(null, args);
  }, { module: 'state', action: 'save' });
};

var _tfSentry_getSyncSnapshot = getSyncSnapshot;
getSyncSnapshot = function() {
  var args = arguments;
  return withSentryReporting_('getSyncSnapshot', function() {
    return _tfSentry_getSyncSnapshot.apply(null, args);
  }, { module: 'sync', action: 'snapshot' });
};

var _tfSentry_pushSyncOps = pushSyncOps;
pushSyncOps = function() {
  var args = arguments;
  return withSentryReporting_('pushSyncOps', function() {
    return _tfSentry_pushSyncOps.apply(null, args);
  }, { module: 'sync', action: 'push_ops' });
};

var _tfSentry_importAppState = importAppState;
importAppState = function() {
  var args = arguments;
  return withSentryReporting_('importAppState', function() {
    return _tfSentry_importAppState.apply(null, args);
  }, { module: 'state', action: 'import' });
};

var _tfSentry_resetAppState = resetAppState;
resetAppState = function() {
  var args = arguments;
  return withSentryReporting_('resetAppState', function() {
    return _tfSentry_resetAppState.apply(null, args);
  }, { module: 'state', action: 'reset' });
};

var _tfSentry_getStaffList = getStaffList;
getStaffList = function() {
  var args = arguments;
  return withSentryReporting_('getStaffList', function() {
    return _tfSentry_getStaffList.apply(null, args);
  }, { module: 'staff', action: 'list_staff' });
};

var _tfSentry_addStaffMember = addStaffMember;
addStaffMember = function() {
  var args = arguments;
  return withSentryReporting_('addStaffMember', function() {
    return _tfSentry_addStaffMember.apply(null, args);
  }, { module: 'staff', action: 'add_staff' });
};

var _tfSentry_updateStaffStatus = updateStaffStatus;
updateStaffStatus = function() {
  var args = arguments;
  return withSentryReporting_('updateStaffStatus', function() {
    return _tfSentry_updateStaffStatus.apply(null, args);
  }, { module: 'staff', action: 'update_status' });
};

var _tfSentry_getAppSettings = getAppSettings;
getAppSettings = function() {
  var args = arguments;
  return withSentryReporting_('getAppSettings', function() {
    return _tfSentry_getAppSettings.apply(null, args);
  }, { module: 'settings', action: 'load' });
};

var _tfSentry_saveAppSettings = saveAppSettings;
saveAppSettings = function() {
  var args = arguments;
  return withSentryReporting_('saveAppSettings', function() {
    return _tfSentry_saveAppSettings.apply(null, args);
  }, { module: 'settings', action: 'save' });
};

var _tfSentry_setupOrRepairSheets = setupOrRepairSheets;
setupOrRepairSheets = function() {
  var args = arguments;
  return withSentryReporting_('setupOrRepairSheets', function() {
    return _tfSentry_setupOrRepairSheets.apply(null, args);
  }, { module: 'sheets', action: 'setup_or_repair' });
};

var _tfSentry_getInventoryData = getInventoryData;
getInventoryData = function() {
  var args = arguments;
  return withSentryReporting_('getInventoryData', function() {
    return _tfSentry_getInventoryData.apply(null, args);
  }, { module: 'inventory', action: 'load_inventory' });
};

var _tfSentry_recordSale = recordSale;
recordSale = function() {
  var args = arguments;
  return withSentryReporting_('recordSale', function() {
    return _tfSentry_recordSale.apply(null, args);
  }, { module: 'inventory', action: 'record_sale' });
};

var _tfSentry_recordRestock = recordRestock;
recordRestock = function() {
  var args = arguments;
  return withSentryReporting_('recordRestock', function() {
    return _tfSentry_recordRestock.apply(null, args);
  }, { module: 'inventory', action: 'record_restock' });
};

var _tfSentry_exportReportTablesToSheets = exportReportTablesToSheets;
exportReportTablesToSheets = function() {
  var args = arguments;
  return withSentryReporting_('exportReportTablesToSheets', function() {
    return _tfSentry_exportReportTablesToSheets.apply(null, args);
  }, { module: 'reports', action: 'export_tables' });
};
