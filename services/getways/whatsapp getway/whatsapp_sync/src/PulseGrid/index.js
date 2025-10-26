// PulseGrid entry point
const PulseGrid = require('./core/PulseGrid');

class PulseGridApp {
  constructor() {
    this.pulseGrid = new PulseGrid();
  }

  async start() {
    await this.pulseGrid.start();
  }

  async stop() {
    await this.pulseGrid.stop();
  }
}

module.exports = PulseGridApp;