// Request validation middleware
const validateSyncRequest = (req, res, next) => {
  const { business_id, phone_number } = req.body;

  if (!business_id || typeof business_id !== 'string') {
    return res.status(400).json({ error: 'Invalid or missing business_id' });
  }

  if (!phone_number || typeof phone_number !== 'string') {
    return res.status(400).json({ error: 'Invalid or missing phone_number' });
  }

  // E.164 format validation for phone number
  const phoneRegex = /^\+[1-9]\d{1,14}$/;
  if (!phoneRegex.test(phone_number)) {
    return res.status(400).json({ error: 'Invalid phone number format. Use E.164 format.' });
  }

  next();
};

module.exports = { validateSyncRequest };