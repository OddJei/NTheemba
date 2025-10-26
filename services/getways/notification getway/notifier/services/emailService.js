const nodemailer = require('nodemailer');
const config = require('../config');
const logger = require('../utils/logger');

// createTransport configuration is taken from config; default to jsonTransport for dev
const transport = nodemailer.createTransport(
  config.email && config.email.smtp ? config.email.smtp : { jsonTransport: true }
);

async function sendEmail({ to, subject, text, html }) {
  const msg = {
    from: config.email.from || 'no-reply@ntheemba.local',
    to,
    subject,
    text,
    html
  };
  logger.info('emailService.sendEmail', { to, subject });
  return transport.sendMail(msg);
}

module.exports = { sendEmail };
