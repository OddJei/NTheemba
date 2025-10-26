// Session state management
const activeSessions = {};

class Session {
  constructor(businessId, phoneNumber) {
    this.id = `${businessId}-${phoneNumber}`;
    this.businessId = businessId;
    this.phoneNumber = phoneNumber;
    this.status = 'pending';
    this.createdAt = new Date();
    this.updatedAt = new Date();
  }

  toJSON() {
    return {
      id: this.id,
      business_id: this.businessId,
      phone_number: this.phoneNumber,
      status: this.status,
      created_at: this.createdAt.toISOString(),
      updated_at: this.updatedAt.toISOString()
    };
  }
}

module.exports = { Session, activeSessions };