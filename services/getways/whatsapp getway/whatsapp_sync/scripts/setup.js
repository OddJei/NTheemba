// Initial setup script
const fs = require('fs');
const path = require('path');

console.log('Setting up WhatsApp Sync service...');

// Create necessary directories
const dirs = ['logs', 'qrcodes'];
dirs.forEach(dir => {
  const dirPath = path.join(__dirname, '..', dir);
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
    console.log(`Created directory: ${dir}`);
  }
});

console.log('Setup complete!');