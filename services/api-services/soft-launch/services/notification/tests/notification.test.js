const request = require('supertest');
const fs = require('fs');
const path = require('path');

function buildApp(dbFile) {
  process.env.NOTIFICATION_DB_FILE = dbFile;
  process.env.SMTP_JSON = '1';
  process.env.SMS_PROVIDER = 'mock';
  return require('../app');
}

describe('softlaunch-notification', () => {
  test('health', async () => {
    const dbFile = path.join(__dirname, 'tmp_db_health.json');
    if (fs.existsSync(dbFile)) fs.unlinkSync(dbFile);

    const app = buildApp(dbFile);
    const res = await request(app).get('/health');
    expect(res.statusCode).toBe(200);
    expect(res.body.status).toBe('ok');
  });

  test('send sms via /notification/send', async () => {
    const dbFile = path.join(__dirname, 'tmp_db_sms.json');
    if (fs.existsSync(dbFile)) fs.unlinkSync(dbFile);

    const app = buildApp(dbFile);

    const res = await request(app)
      .post('/notification/send')
      .send({
        user_id: 'u1',
        channel: 'sms',
        payload: { to: '+1234567890', message: 'Hello from test' }
      });

    expect(res.statusCode).toBe(201);
    expect(res.body.id).toMatch(/^ntf_/);
    expect(res.body.status).toBe('sent');
  });
});
