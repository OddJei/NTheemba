const dotenv = require('dotenv');
dotenv.config();

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
  email: {
    from: process.env.EMAIL_FROM || 'no-reply@ntheemba.local',
    smtp: smtpConfig
  },
  sms: {
    provider: process.env.SMS_PROVIDER || 'mock',
    sid: process.env.TWILIO_SID,
    token: process.env.TWILIO_TOKEN,
    from: process.env.SMS_FROM
  }
};
