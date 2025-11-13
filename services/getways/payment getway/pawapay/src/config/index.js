module.exports = {
  port: process.env.PORT || 4001,
  pawapay: {
    url: process.env.PAWAPAY_API_URL || 'https://api.pawapay.example',
    apiKey: process.env.PAWAPAY_API_KEY || '',
  },
};
