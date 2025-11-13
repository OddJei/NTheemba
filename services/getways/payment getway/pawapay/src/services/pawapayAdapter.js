const axios = require('axios');

class PawapayAdapter {
  constructor() {
    this.baseUrl = process.env.PAWAPAY_API_URL || 'https://api.pawapay.example';
    this.apiKey = process.env.PAWAPAY_API_KEY || '';
    this.client = axios.create({ baseURL: this.baseUrl, timeout: 30000 });
  }

  async initiatePayment({ amount, currency = 'USD', phone, order_ref }) {
    // Minimal example request payload - adapt to real Pawapay API
    const payload = {
      amount,
      currency,
      phone,
      order_ref,
    };

    // In production: sign request, include headers, handle status codes
    try {
      // If real API exists, replace this with `await this.client.post('/payments', payload, { headers })`
      // For scaffold, simulate a successful response
      return {
        status: 'ok',
        payment_url: `https://pay.pawapay.example/pay/${order_ref || 'r_' + Date.now()}`,
        transaction_ref: `pawapay_${Date.now()}`,
        raw: payload,
      };
    } catch (err) {
      throw new Error(err.message || 'pawapay initiate failed');
    }
  }

  async verifyPayment(transaction_ref) {
    if (!transaction_ref) throw new Error('transaction_ref required');
    // Simulate a verification call. Replace with real HTTP call to Pawapay verify endpoint.
    try {
      // Example: const resp = await this.client.get(`/payments/${transaction_ref}`, { headers })
      return {
        status: 'success',
        transaction_ref,
        verified_at: new Date().toISOString(),
      };
    } catch (err) {
      throw new Error(err.message || 'pawapay verify failed');
    }
  }
}

module.exports = PawapayAdapter;
