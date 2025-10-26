// Strategy class
class Strategy {
  constructor(limit = 10) {
    this.limit = limit;
  }

  getEligible(session, recipients) {
    // Return eligible recipients up to limit
    return recipients.slice(0, this.limit);
  }
}

module.exports = Strategy;