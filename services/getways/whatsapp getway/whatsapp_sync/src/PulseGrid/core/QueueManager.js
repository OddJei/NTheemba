// QueueManager class
class QueueManager {
  constructor() {
    this.queues = {};
  }

  add(session, recipient, message) {
    // Add message to queue
  }

  getNext(session, recipient) {
    // Get next message from queue
  }

  markSent(session, recipient) {
    // Mark message as sent
  }
}

module.exports = QueueManager;