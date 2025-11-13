const axios = require('axios');

class ZamtelAdapter {
  constructor() {
    this.baseUrl = process.env.ZAMTEL_API_URL || 'https://api.zamtel.example';
    this.apiKey = process.env.ZAMTEL_API_KEY || '';
    this.client = axios.create({ baseURL: this.baseUrl, timeout: 30000 });
  }

  async initiatePayment({ amount, currency = 'USD', phone, order_ref }) {
    const payload = { amount, currency, phone, order_ref };
    try {
      // Replace with real Zamtel API call
      return {
        status: 'ok',
        payment_url: `https://pay.zamtel.example/pay/${order_ref || 'r_' + Date.now()}`,
        transaction_ref: `zamtel_${Date.now()}`,
        raw: payload,
      };
    } catch (err) {
      throw new Error(err.message || 'zamtel initiate failed');
    }
  }

  async verifyPayment(transaction_ref) {
    if (!transaction_ref) throw new Error('transaction_ref required');
    try {
      return {
        status: 'success',
        transaction_ref,
        verified_at: new Date().toISOString(),
      };
    } catch (err) {
      throw new Error(err.message || 'zamtel verify failed');
    }
  }
}

module.exports = ZamtelAdapter;
