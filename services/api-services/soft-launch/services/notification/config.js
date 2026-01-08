require('dotenv').config();

const useJsonTransport = process.env.SMTP_JSON === '1' || process.env.SMTP_JSON === 'true';

const smtpConfig = useJsonTransport
  ? { jsonTransport: true }
  : {
      host: process.env.EMAIL_SMTP_HOST || 'smtp.mailgun.org',
      port: parseInt(process.env.EMAIL_SMTP_PORT || '587', 10),
      secure: false,
      auth: {
        user: process.env.MAIL_USER,
        pass: process.env.MAIL_PASS
      }
    };

module.exports = {
  dbFile: process.env.NOTIFICATION_DB_FILE || './dev_notifications.json',
  email: {
    from: process.env.EMAIL_FROM || 'no-reply@ntheemba.local',
    smtp: smtpConfig
  },
  sms: {
    provider: process.env.SMS_PROVIDER || 'mock',
    from: process.env.SMS_FROM,
    textbee: {
      baseUrl: process.env.TEXTBEE_BASE_URL || 'https://api.textbee.dev/api/v1',
      apiKey: process.env.TEXTBEE_API_KEY,
      deviceId: process.env.TEXTBEE_DEVICE_ID
    }
  }
};
