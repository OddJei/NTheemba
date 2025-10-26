const path = require('path');
const fs = require('fs').promises;
const fetch = require('node-fetch');
const fileManager = require('../utils/fileManager');

class QRCodeService {
  constructor() {
    this.qrDir = path.join(__dirname, '../../qrcodes');
  }

  async getQRUrl(sessionId) {
    // For the new flow, QR codes are available when business sync status is pending
    // The sessionId format is businessId-phoneNumber
    const parts = sessionId.split('-');
    if (parts.length >= 2) {
      const businessId = parts[0];
      try {
        // Check if business sync status is pending
        const response = await fetch(`${process.env.API_BASE_URL || 'http://api:8000'}/synced_businesses/${businessId}`);
        if (response.ok) {
          const business = await response.json();
          if (business.sync_status === 'pending') {
            const filePath = path.join(this.qrDir, `${sessionId}.png`);
            const fs = require('fs').promises;
            try {
              await fs.access(filePath);
              return `/get_qrd/${sessionId}`;
            } catch {
              // QR file doesn't exist yet, but business is pending sync
              return `/get_qrd/${sessionId}`;
            }
          }
        }
      } catch (error) {
        console.error('Error checking business sync status:', error);
      }
    }
    return null;
  }

  async getQRFile(sessionId) {
    const filePath = path.join(this.qrDir, `${sessionId}.png`);
    try {
      await fs.access(filePath);
      return { filePath };
    } catch {
      return null;
    }
  }

  async deleteQRCode(sessionId) {
    const filePath = path.join(this.qrDir, `${sessionId}.png`);
    try {
      await fs.unlink(filePath);
      return true;
    } catch {
      return false;
    }
  }

  // Future: generate QR code programmatically
  async generateQRCode(sessionId, qrData) {
    // Implementation for QR code generation
    // This would integrate with a QR library
  }
}

module.exports = new QRCodeService();