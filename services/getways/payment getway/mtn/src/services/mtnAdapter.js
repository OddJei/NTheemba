const axios = require('axios');

class MtnAdapter {
  constructor() {
    this.baseUrl = process.env.MTN_API_URL || 'https://api.mtn.example';
    this.apiKey = process.env.MTN_API_KEY || '';
    this.client = axios.create({ baseURL: this.baseUrl, timeout: 30000 });
  }

  async initiatePayment({ amount, currency = 'USD', phone, order_ref }) {
    const payload = { amount, currency, phone, order_ref };
    try {
      // Replace with real MTN API call
      return {
        status: 'ok',
        payment_url: `https://pay.mtn.example/pay/${order_ref || 'r_' + Date.now()}`,
        transaction_ref: `mtn_${Date.now()}`,
        raw: payload,
      };
    } catch (err) {
      throw new Error(err.message || 'mtn initiate failed');
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
      throw new Error(err.message || 'mtn verify failed');
    }
  }
}

module.exports = MtnAdapter;
