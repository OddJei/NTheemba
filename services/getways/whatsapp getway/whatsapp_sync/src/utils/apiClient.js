const axios = require('axios');

const BASE_URL = process.env.API_BASE_URL || 'http://api:8000';

class ApiClient {
  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      timeout: 10000, // 10 seconds
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      response => response,
      error => {
        const logger = require('./logger');
        logger.error('api_request_failed', error.message, {
          url: error.config?.url,
          method: error.config?.method,
          status: error.response?.status
        });
        return Promise.reject(error);
      }
    );
  }

  async get(url, config = {}) {
    return this.client.get(url, config);
  }

  async post(url, data = null, config = {}) {
    return this.client.post(url, data, config);
  }

  async put(url, data = null, config = {}) {
    return this.client.put(url, data, config);
  }

  async delete(url, config = {}) {
    return this.client.delete(url, config);
  }
}

module.exports = new ApiClient();