const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const { sendEmail } = require('./services/emailService');
const { sendSMS } = require('./services/smsService');

const packageDef = protoLoader.loadSync('./proto/notifier.proto');
const grpcObj = grpc.loadPackageDefinition(packageDef);
const notifierPackage = grpcObj.notifier;

function sendEmailHandler(call, callback) {
  const { to, subject, message, html } = call.request;
  sendEmail({ to, subject, text: message, html })
    .then(() => callback(null, { ok: true, status: 'email_sent' }))
    .catch((err) => callback(null, { ok: false, status: 'email_failed', error: err.message }));
}

function sendSMSHandler(call, callback) {
  const { to, message } = call.request;
  sendSMS({ to, message })
    .then(() => callback(null, { ok: true, status: 'sms_sent' }))
    .catch((err) => callback(null, { ok: false, status: 'sms_failed', error: err.message }));
}

const server = new grpc.Server();
server.addService(notifierPackage.Notifier.service, {
  SendEmail: sendEmailHandler,
  SendSMS: sendSMSHandler
});

server.bindAsync('0.0.0.0:50051', grpc.ServerCredentials.createInsecure(), () => {
  console.log('gRPC Notifier running on port 50051');
  server.start();
});
