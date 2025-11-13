const axios = require('axios');

class AirtelAdapter {
  constructor() {
    this.baseUrl = process.env.AIRTEL_API_URL || 'https://api.airtel.example';
    this.apiKey = process.env.AIRTEL_API_KEY || '';
    this.client = axios.create({ baseURL: this.baseUrl, timeout: 30000 });
  }

  async initiatePayment({ amount, currency = 'USD', phone, order_ref }) {
    const payload = { amount, currency, phone, order_ref };
    try {
      // Replace with real Airtel API call
      return {
        status: 'ok',
        payment_url: `https://pay.airtel.example/pay/${order_ref || 'r_' + Date.now()}`,
        transaction_ref: `airtel_${Date.now()}`,
        raw: payload,
      };
    } catch (err) {
      throw new Error(err.message || 'airtel initiate failed');
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
      throw new Error(err.message || 'airtel verify failed');
    }
  }
}

module.exports = AirtelAdapter;
