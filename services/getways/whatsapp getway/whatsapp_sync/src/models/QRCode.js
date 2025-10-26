class QRCode {
  constructor(sessionId, filePath) {
    this.sessionId = sessionId;
    this.filePath = filePath;
    this.createdAt = new Date();
    this.expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours
  }

  isExpired() {
    return new Date() > this.expiresAt;
  }

  toJSON() {
    return {
      session_id: this.sessionId,
      file_path: this.filePath,
      created_at: this.createdAt.toISOString(),
      expires_at: this.expiresAt.toISOString(),
      expired: this.isExpired()
    };
  }
}

module.exports = QRCode;