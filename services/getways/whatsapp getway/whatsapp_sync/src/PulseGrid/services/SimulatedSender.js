// SimulatedSender class
class SimulatedSender {
  async send(session, recipient, message) {
    console.log(`[SimulatedSender] Sending to ${recipient} in session ${session}:`, message);
    return true;
  }
}

module.exports = SimulatedSender;