const apiClient = require('../utils/apiClient');
const sessionService = require('./sessionService');
const qrCodeService = require('./qrCodeService');
const logger = require('../utils/logger');
const fetch = require('node-fetch');

class WhatsAppSyncService {
  async startSync({ business_id, phone_number }) {
    if (!business_id || !phone_number) {
      logger.log('error', 'sync_request_invalid', '❌ Missing required parameters!', { business_id, phone_number });
      throw new Error('❌ Missing required parameters!');
    }

    try {
      // Create synced business with pending status
      await apiClient.post('/synced_businesses/sync', null, {
        params: {
          business_id: business_id,
          phone_number: phone_number
        }
      });

      logger.log('info', 'sync_request', `🔄 Sync request created for ${business_id}`, { business_id, phone_number });

      return {
        status: '✅ Sync request created!',
        business_id,
        phone_number,
        message: 'QR code will be available shortly.'
      };
    } catch (error) {
      logger.log('error', 'sync_request_failed', `❌ Sync failed for ${business_id}`, {
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  async createSyncedBusiness(businessId, phoneNumber) {
    await apiClient.post('/synced_businesses/sync', null, {
      params: {
        business_id: businessId,
        phone_number: phoneNumber,
        sync_status: 'pending'
      }
    });
  }

  async getQRCode(sessionId) {
    // Check if QR file exists first
    let qrFile = await qrCodeService.getQRFile(sessionId);
    if (qrFile) {
      return qrFile;
    }

    // If QR doesn't exist, check if we should start a session
    const parts = sessionId.split('-');
    if (parts.length >= 2) {
      const businessId = parts[0];
      const phoneNumber = parts.slice(1).join('-'); // Handle phone numbers with dashes

      try {
        // Check business sync status
        const response = await fetch(`${process.env.API_BASE_URL || 'http://api:8000'}/synced_businesses/${businessId}`);
        if (response.ok) {
          const business = await response.json();
          if (business.sync_status === 'pending') {
            // Business is pending sync, start the session to generate QR
            logger.log('info', 'qr_session_start', `Starting session for pending business ${businessId}`);
            await sessionService.startSession(businessId, phoneNumber);

            // Wait a bit for QR to be generated, then check again
            await new Promise(resolve => setTimeout(resolve, 3000));
            qrFile = await qrCodeService.getQRFile(sessionId);
            if (qrFile) {
              return qrFile;
            }
          }
        }
      } catch (error) {
        logger.log('error', 'qr_session_start_failed', `Failed to start session for QR: ${error.message}`);
      }
    }

    return null;
  }

  async getSessionStatus(sessionId) {
    const isActive = sessionService.isSessionActive(sessionId);
    return {
      session_id: sessionId,
      status: isActive ? 'active' : 'pending'
    };
  }

  async deleteQRCode(sessionId) {
    const deleted = await qrCodeService.deleteQRCode(sessionId);
    if (deleted) {
      logger.log('info', 'qr_deleted', `🧹 QR code deleted for ${sessionId}`);
      return { status: 'deleted' };
    } else {
      return { error: 'QR code not found' };
    }
  }
}

module.exports = new WhatsAppSyncService();