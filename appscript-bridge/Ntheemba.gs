/**
 * Protected Ntheemba V1 bridge contract for approved TradeFlow deployments.
 * This file adds an API boundary only; it is not a TradeFlow product baseline.
 */

var NTHEEMBA_API_VERSION = '2026-07-12';
var NTHEEMBA_SHEETS = {
  config: ['Key', 'Value', 'Updated At'],
  faqs: ['FAQ ID', 'Question', 'Approved Answer', 'Keywords', 'Public', 'Updated At'],
  catalogue: ['Item ID', 'Item Type', 'Public', 'Display Name', 'Description', 'Image URL', 'Category', 'Price Override', 'Availability Override', 'Duration Minutes', 'Qualified Staff IDs'],
  availability: ['Slot ID', 'Service ID', 'Date', 'Start Time', 'End Time', 'Staff ID', 'Status', 'Updated At'],
  orders: ['Request ID', 'Idempotency Key', 'Customer ID', 'Product ID', 'Quantity', 'Fulfilment Method', 'Customer Name', 'Contact Number', 'Delivery Details', 'Status', 'Created At', 'Updated At'],
  bookings: ['Request ID', 'Idempotency Key', 'Customer ID', 'Service ID', 'Date', 'Start Time', 'Staff ID', 'Customer Name', 'Contact Number', 'Status', 'Created At', 'Updated At'],
  audit: ['Event ID', 'Request ID', 'Business ID', 'Customer ID', 'Action', 'Outcome', 'Details JSON', 'Created At']
};

function doPost(e) {
  var requestId = '';
  try {
    var body = _ntheembaParseRequest_(e);
    requestId = _normalizeString(body.request_id) || Utilities.getUuid();
    _ntheembaAuthorize_(body);
    var data = _ntheembaRoute_(body.action, body.data || {}, body);
    _ntheembaWriteAudit_(requestId, body, 'success', { action: body.action });
    return _ntheembaJson_({
      ok: true,
      api_version: NTHEEMBA_API_VERSION,
      request_id: requestId,
      business_id: _ntheembaBusinessId_(),
      data: data
    });
  } catch (error) {
    try {
      _ntheembaWriteAudit_(requestId || Utilities.getUuid(), {}, 'error', {
        message: String(error && error.message || error).slice(0, 500)
      });
    } catch (ignored) {}
    return _ntheembaJson_({
      ok: false,
      api_version: NTHEEMBA_API_VERSION,
      request_id: requestId,
      error: {
        code: error && error.code || 'INTERNAL_ERROR',
        message: error && error.publicMessage || 'The TradeFlow integration could not complete the request.'
      }
    });
  }
}

function setupNtheembaIntegration() {
  _ntheembaEnsureSheets_();
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('NTHEEMBA_API_TOKEN');
  var businessId = props.getProperty('NTHEEMBA_BUSINESS_ID');
  if (!token || token.length < 32) {
    throw new Error('Set NTHEEMBA_API_TOKEN in Script Properties to a random value of at least 32 characters.');
  }
  if (!businessId) throw new Error('Set NTHEEMBA_BUSINESS_ID in Script Properties.');
  return { success: true, businessId: businessId, apiVersion: NTHEEMBA_API_VERSION };
}

function _ntheembaParseRequest_(e) {
  if (!e || !e.postData || !e.postData.contents) {
    throw _ntheembaError_('INVALID_REQUEST', 'A JSON request body is required.');
  }
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (error) {
    throw _ntheembaError_('INVALID_JSON', 'The request body must be valid JSON.');
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    throw _ntheembaError_('INVALID_REQUEST', 'The request body must be a JSON object.');
  }
  if (!_normalizeString(body.action)) throw _ntheembaError_('ACTION_REQUIRED', 'An action is required.');
  return body;
}

function _ntheembaAuthorize_(body) {
  var props = PropertiesService.getScriptProperties();
  var expectedToken = _normalizeString(props.getProperty('NTHEEMBA_API_TOKEN'));
  var expectedBusiness = _normalizeString(props.getProperty('NTHEEMBA_BUSINESS_ID'));
  var providedToken = _normalizeString(body.api_token);
  var providedBusiness = _normalizeString(body.business_id);
  if (!expectedToken || expectedToken.length < 32 || !_ntheembaSafeEquals_(expectedToken, providedToken)) {
    throw _ntheembaError_('UNAUTHORIZED', 'The integration credentials are invalid.');
  }
  if (!expectedBusiness || !providedBusiness || expectedBusiness !== providedBusiness) {
    throw _ntheembaError_('BUSINESS_MISMATCH', 'The request is not valid for this TradeFlow deployment.');
  }
}

function _ntheembaSafeEquals_(expected, actual) {
  expected = String(expected || '');
  actual = String(actual || '');
  var mismatch = expected.length ^ actual.length;
  var length = Math.max(expected.length, actual.length);
  for (var i = 0; i < length; i++) {
    mismatch |= (expected.charCodeAt(i % Math.max(1, expected.length)) || 0) ^
      (actual.charCodeAt(i % Math.max(1, actual.length)) || 0);
  }
  return mismatch === 0;
}

function _ntheembaRoute_(action, data, request) {
  action = _normalizeString(action).toLowerCase();
  var routes = {
    health: function() { return { status: 'ready', api_version: NTHEEMBA_API_VERSION }; },
    business_info: function() { return _ntheembaBusinessInfo_(); },
    business_hours: function() { return _ntheembaBusinessHours_(data.at); },
    search_faqs: function() { return _ntheembaSearchFaqs_(data.query); },
    search_catalogue: function() { return _ntheembaSearchCatalogue_(data); },
    get_item: function() { return _ntheembaGetPublicItem_(data.item_id, data.item_type); },
    product_availability: function() { return _ntheembaProductAvailability_(data.product_id, data.quantity); },
    available_slots: function() { return _ntheembaAvailableSlots_(data.service_id, data.date); },
    validate_booking: function() { return _ntheembaValidateBooking_(data); },
    create_order_request: function() { return _ntheembaCreateOrder_(data, request); },
    create_booking_request: function() { return _ntheembaCreateBooking_(data, request); },
    request_status: function() { return _ntheembaRequestStatus_(data.request_id, data.request_type); },
    audit_event: function() {
      _ntheembaWriteAudit_(request.request_id || Utilities.getUuid(), request, data.outcome || 'recorded', data);
      return { recorded: true };
    }
  };
  if (!routes[action]) throw _ntheembaError_('UNSUPPORTED_ACTION', 'This integration action is not supported.');
  return routes[action]();
}

function _ntheembaEnsureSheets_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  _ensureSheet(ss, 'NtheembaConfig', NTHEEMBA_SHEETS.config);
  _ensureSheet(ss, 'NtheembaFAQs', NTHEEMBA_SHEETS.faqs);
  _ensureSheet(ss, 'NtheembaCatalogue', NTHEEMBA_SHEETS.catalogue);
  _ensureSheet(ss, 'NtheembaAvailability', NTHEEMBA_SHEETS.availability);
  _ensureSheet(ss, 'NtheembaOrderRequests', NTHEEMBA_SHEETS.orders);
  _ensureSheet(ss, 'NtheembaBookingRequests', NTHEEMBA_SHEETS.bookings);
  _ensureSheet(ss, 'NtheembaAudit', NTHEEMBA_SHEETS.audit);
}

function _ntheembaConfig_() {
  _ntheembaEnsureSheets_();
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('NtheembaConfig');
  var config = {};
  _getSheetData(sheet, 2, null, 2).forEach(function(row) {
    var key = _normalizeString(row[0]).toLowerCase();
    if (!key) return;
    var value = row[1];
    var parsed = _parseJson(value);
    config[key] = parsed === null ? value : parsed;
  });
  return config;
}

function _ntheembaBusinessInfo_() {
  var app = getAppSettings();
  var config = _ntheembaConfig_();
  return {
    business_id: _ntheembaBusinessId_(),
    name: _normalizeString(config.business_name || app.businessName),
    location: _normalizeString(config.location || app.businessAddress),
    contact_phone: _normalizeString(config.contact_phone || app.businessWhatsapp),
    contact_email: _normalizeString(config.contact_email),
    description: _normalizeString(config.description),
    categories: Array.isArray(config.public_categories) ? config.public_categories.slice(0, 100) : [],
    fulfilment_methods: Array.isArray(config.fulfilment_methods) ? config.fulfilment_methods : ['collection'],
    handover_enabled: config.handover_enabled !== false
  };
}

function _ntheembaBusinessHours_(at) {
  var config = _ntheembaConfig_();
  var weekly = config.weekly_hours && typeof config.weekly_hours === 'object' ? config.weekly_hours : {};
  var closures = Array.isArray(config.special_closures) ? config.special_closures : [];
  var date = at ? new Date(at) : new Date();
  if (isNaN(date.getTime())) throw _ntheembaError_('INVALID_DATE', 'The supplied date is invalid.');
  var timezone = _normalizeString(config.timezone) || Session.getScriptTimeZone();
  var dateKey = Utilities.formatDate(date, timezone, 'yyyy-MM-dd');
  var dayKey = Utilities.formatDate(date, timezone, 'EEEE').toLowerCase();
  var timeKey = Utilities.formatDate(date, timezone, 'HH:mm');
  var special = closures.filter(function(item) { return _normalizeString(item.date) === dateKey; })[0];
  var hours = special || weekly[dayKey] || { closed: true };
  var isOpen = !hours.closed && _normalizeString(hours.open) && _normalizeString(hours.close) &&
    timeKey >= String(hours.open) && timeKey < String(hours.close);
  return {
    timezone: timezone,
    checked_at: date.toISOString(),
    date: dateKey,
    day: dayKey,
    is_open: Boolean(isOpen),
    opens_at: hours.closed ? null : hours.open || null,
    closes_at: hours.closed ? null : hours.close || null,
    special_closure: Boolean(special && special.closed),
    note: _normalizeString(hours.note)
  };
}

function _ntheembaSearchFaqs_(query) {
  _ntheembaEnsureSheets_();
  var terms = _ntheembaTerms_(query);
  var rows = _getSheetData(SpreadsheetApp.getActiveSpreadsheet().getSheetByName('NtheembaFAQs'), 2, null, 6);
  return rows.filter(function(row) {
    if (!_isTruthy(row[4])) return false;
    if (!terms.length) return true;
    var haystack = [row[1], row[2], row[3]].join(' ').toLowerCase();
    return terms.some(function(term) { return haystack.indexOf(term) !== -1; });
  }).slice(0, 10).map(function(row) {
    return { faq_id: _normalizeString(row[0]), question: _normalizeString(row[1]), answer: _normalizeString(row[2]) };
  });
}

function _ntheembaCatalogueRows_() {
  _ntheembaEnsureSheets_();
  return _getSheetData(SpreadsheetApp.getActiveSpreadsheet().getSheetByName('NtheembaCatalogue'), 2, null, 11)
    .filter(function(row) { return _normalizeString(row[0]) && _isTruthy(row[2]); });
}

function _ntheembaSearchCatalogue_(data) {
  var terms = _ntheembaTerms_(data.query);
  var type = _normalizeString(data.item_type).toLowerCase();
  var category = _normalizeString(data.category).toLowerCase();
  return _ntheembaCatalogueRows_().filter(function(row) {
    var rowType = _normalizeString(row[1]).toLowerCase();
    if (type && rowType !== type) return false;
    if (category && _normalizeString(row[6]).toLowerCase() !== category) return false;
    if (!terms.length) return true;
    var haystack = [row[0], row[3], row[4], row[6]].join(' ').toLowerCase();
    return terms.every(function(term) { return haystack.indexOf(term) !== -1; });
  }).slice(0, 20).map(_ntheembaPublicItemFromRow_);
}

function _ntheembaGetPublicItem_(itemId, itemType) {
  itemId = _normalizeString(itemId);
  itemType = _normalizeString(itemType).toLowerCase();
  var row = _ntheembaCatalogueRows_().filter(function(candidate) {
    return _normalizeString(candidate[0]) === itemId &&
      (!itemType || _normalizeString(candidate[1]).toLowerCase() === itemType);
  })[0];
  if (!row) throw _ntheembaError_('ITEM_NOT_FOUND', 'The requested public item was not found.');
  return _ntheembaPublicItemFromRow_(row);
}

function _ntheembaPublicItemFromRow_(row) {
  var itemId = _normalizeString(row[0]);
  var itemType = _normalizeString(row[1]).toLowerCase();
  var price = row[7] === '' ? null : Number(row[7]);
  var available = row[8] === '' ? null : _isTruthy(row[8]);
  if (itemType === 'product') {
    var product = getProductById(itemId);
    if (!product) throw _ntheembaError_('ITEM_NOT_FOUND', 'The public product no longer exists.');
    if (price === null || isNaN(price)) price = Number(product.sellingPrice || product.unitPrice || 0);
    var stock = Number(getProductStock(itemId) || 0);
    if (available === null) available = stock > 0;
  }
  return {
    item_id: itemId,
    item_type: itemType,
    name: _normalizeString(row[3]),
    description: _normalizeString(row[4]),
    image_url: _normalizeString(row[5]),
    category: _normalizeString(row[6]),
    price: price === null || isNaN(price) ? null : price,
    available: Boolean(available),
    duration_minutes: itemType === 'service' ? Number(row[9] || 0) : null
  };
}

function _ntheembaProductAvailability_(productId, quantity) {
  var item = _ntheembaGetPublicItem_(productId, 'product');
  var stock = Math.max(0, Number(getProductStock(productId) || 0));
  var requested = Math.max(1, Number(quantity || 1));
  return {
    product_id: item.item_id,
    available: item.available && stock >= requested,
    requested_quantity: requested,
    available_quantity: stock
  };
}

function _ntheembaAvailableSlots_(serviceId, date) {
  _ntheembaGetPublicItem_(serviceId, 'service');
  date = _normalizeString(date);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw _ntheembaError_('INVALID_DATE', 'A date in YYYY-MM-DD format is required.');
  _ntheembaEnsureSheets_();
  var rows = _getSheetData(SpreadsheetApp.getActiveSpreadsheet().getSheetByName('NtheembaAvailability'), 2, null, 8);
  return rows.filter(function(row) {
    return _normalizeString(row[1]) === serviceId && _toDateOnly(row[2]) === date &&
      _normalizeString(row[6]).toLowerCase() === 'available';
  }).map(function(row) {
    return {
      slot_id: _normalizeString(row[0]),
      service_id: serviceId,
      date: date,
      start_time: _normalizeString(row[3]),
      end_time: _normalizeString(row[4]),
      staff_id: _normalizeString(row[5]) || null
    };
  });
}

function _ntheembaValidateBooking_(data) {
  var slots = _ntheembaAvailableSlots_(_normalizeString(data.service_id), _normalizeString(data.date));
  var match = slots.filter(function(slot) {
    return slot.start_time === _normalizeString(data.start_time) &&
      (!data.staff_id || slot.staff_id === _normalizeString(data.staff_id));
  })[0];
  return { valid: Boolean(match), slot: match || null };
}

function _ntheembaCreateOrder_(data, request) {
  var productId = _normalizeString(data.product_id);
  var quantity = Number(data.quantity || 0);
  if (!productId || quantity <= 0 || Math.floor(quantity) !== quantity) {
    throw _ntheembaError_('INVALID_ORDER', 'A product and positive whole-number quantity are required.');
  }
  var availability = _ntheembaProductAvailability_(productId, quantity);
  if (!availability.available) throw _ntheembaError_('PRODUCT_UNAVAILABLE', 'The requested quantity is not currently available.');
  var config = _ntheembaConfig_();
  var methods = Array.isArray(config.fulfilment_methods) ? config.fulfilment_methods : ['collection'];
  var fulfilment = _normalizeString(data.fulfilment_method).toLowerCase();
  if (methods.indexOf(fulfilment) === -1) throw _ntheembaError_('INVALID_FULFILMENT', 'The requested fulfilment method is not available.');
  if (!_normalizeString(data.customer_name) || !_normalizeString(data.contact_number)) {
    throw _ntheembaError_('CUSTOMER_DETAILS_REQUIRED', 'Customer name and contact number are required.');
  }
  if (fulfilment === 'delivery' && !_normalizeString(data.delivery_details)) {
    throw _ntheembaError_('DELIVERY_DETAILS_REQUIRED', 'Delivery details are required.');
  }
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('NtheembaOrderRequests');
    var idempotency = _normalizeString(request.idempotency_key || data.idempotency_key);
    var existing = _ntheembaFindByIdempotency_(sheet, idempotency);
    if (existing) return { request_id: existing[0], status: existing[9], duplicate: true };
    var now = new Date();
    var requestId = 'ORD-' + Utilities.getUuid();
    sheet.appendRow([requestId, idempotency, _normalizeString(request.customer_id), productId, quantity,
      fulfilment, _normalizeString(data.customer_name), _normalizeString(data.contact_number),
      _normalizeString(data.delivery_details), 'submitted', now, now]);
    return { request_id: requestId, request_type: 'order', status: 'submitted' };
  } finally {
    lock.releaseLock();
  }
}

function _ntheembaCreateBooking_(data, request) {
  var validation = _ntheembaValidateBooking_(data);
  if (!validation.valid) throw _ntheembaError_('SLOT_UNAVAILABLE', 'The selected appointment slot is no longer available.');
  if (!_normalizeString(data.customer_name) || !_normalizeString(data.contact_number)) {
    throw _ntheembaError_('CUSTOMER_DETAILS_REQUIRED', 'Customer name and contact number are required.');
  }
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('NtheembaBookingRequests');
    var idempotency = _normalizeString(request.idempotency_key || data.idempotency_key);
    var existing = _ntheembaFindByIdempotency_(sheet, idempotency);
    if (existing) return { request_id: existing[0], status: existing[9], duplicate: true };
    validation = _ntheembaValidateBooking_(data);
    if (!validation.valid) throw _ntheembaError_('SLOT_UNAVAILABLE', 'The selected appointment slot is no longer available.');
    var now = new Date();
    var requestId = 'BKG-' + Utilities.getUuid();
    sheet.appendRow([requestId, idempotency, _normalizeString(request.customer_id), _normalizeString(data.service_id),
      _normalizeString(data.date), _normalizeString(data.start_time), _normalizeString(data.staff_id),
      _normalizeString(data.customer_name), _normalizeString(data.contact_number), 'submitted', now, now]);
    _ntheembaMarkSlotRequested_(validation.slot.slot_id);
    return { request_id: requestId, request_type: 'booking', status: 'submitted' };
  } finally {
    lock.releaseLock();
  }
}

function _ntheembaRequestStatus_(requestId, requestType) {
  requestId = _normalizeString(requestId);
  requestType = _normalizeString(requestType).toLowerCase();
  var sheetName = requestType === 'booking' ? 'NtheembaBookingRequests' : 'NtheembaOrderRequests';
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  var row = _getSheetData(sheet, 2, null, 12).filter(function(item) { return _normalizeString(item[0]) === requestId; })[0];
  if (!row) throw _ntheembaError_('REQUEST_NOT_FOUND', 'The customer request was not found.');
  return { request_id: requestId, request_type: requestType || 'order', status: _normalizeString(row[9]), updated_at: _serializeDate(row[11]) };
}

function _ntheembaFindByIdempotency_(sheet, idempotency) {
  if (!idempotency) throw _ntheembaError_('IDEMPOTENCY_REQUIRED', 'An idempotency key is required for record creation.');
  return _getSheetData(sheet, 2, null, 12).filter(function(row) { return _normalizeString(row[1]) === idempotency; })[0] || null;
}

function _ntheembaMarkSlotRequested_(slotId) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('NtheembaAvailability');
  var rows = _getSheetData(sheet, 2, null, 8);
  for (var i = 0; i < rows.length; i++) {
    if (_normalizeString(rows[i][0]) === slotId) {
      sheet.getRange(i + 2, 7, 1, 2).setValues([['requested', new Date()]]);
      return;
    }
  }
}

function _ntheembaWriteAudit_(requestId, request, outcome, details) {
  _ntheembaEnsureSheets_();
  var safeDetails = _ntheembaRedact_(details || {});
  SpreadsheetApp.getActiveSpreadsheet().getSheetByName('NtheembaAudit').appendRow([
    'EVT-' + Utilities.getUuid(), requestId, _ntheembaBusinessId_(),
    _normalizeString(request && request.customer_id), _normalizeString(request && request.action),
    _normalizeString(outcome), JSON.stringify(safeDetails).slice(0, 10000), new Date()
  ]);
}

function _ntheembaRedact_(value) {
  var blocked = /token|secret|password|cost|margin|profit|supplier|payroll|internal|authorization/i;
  if (Array.isArray(value)) return value.slice(0, 100).map(_ntheembaRedact_);
  if (!value || typeof value !== 'object') return typeof value === 'string' ? value.slice(0, 1000) : value;
  var output = {};
  Object.keys(value).forEach(function(key) {
    if (!blocked.test(key)) output[key] = _ntheembaRedact_(value[key]);
  });
  return output;
}

function _ntheembaTerms_(query) {
  return _normalizeString(query).toLowerCase().split(/\s+/).filter(function(term) { return term.length > 1; }).slice(0, 12);
}

function _ntheembaBusinessId_() {
  return _normalizeString(PropertiesService.getScriptProperties().getProperty('NTHEEMBA_BUSINESS_ID'));
}

function _ntheembaError_(code, publicMessage) {
  var error = new Error(publicMessage);
  error.code = code;
  error.publicMessage = publicMessage;
  return error;
}

function _ntheembaJson_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}
