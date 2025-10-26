class Business {
  constructor(id, phoneNumber) {
    this.id = id;
    this.phoneNumber = phoneNumber;
    this.syncStatus = 'pending';
    this.createdAt = new Date();
    this.updatedAt = new Date();
  }

  toJSON() {
    return {
      id: this.id,
      phone_number: this.phoneNumber,
      sync_status: this.syncStatus,
      created_at: this.createdAt.toISOString(),
      updated_at: this.updatedAt.toISOString()
    };
  }
}

module.exports = Business;