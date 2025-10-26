const requireApiKey = (req, res, next) => {
  const key = req.headers['x-api-key'];
  const expectedKey = process.env.WHATSAPP_API_KEY;

  if (!key || key !== expectedKey) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
};

module.exports = { requireApiKey };