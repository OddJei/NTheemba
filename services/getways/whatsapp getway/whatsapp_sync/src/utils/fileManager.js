const fs = require('fs').promises;
const path = require('path');

class FileManager {
  constructor(baseDir = './') {
    this.baseDir = path.resolve(baseDir);
  }

  async readFile(filePath) {
    const fullPath = path.join(this.baseDir, filePath);
    return fs.readFile(fullPath, 'utf8');
  }

  async writeFile(filePath, content) {
    const fullPath = path.join(this.baseDir, filePath);
    await fs.mkdir(path.dirname(fullPath), { recursive: true });
    return fs.writeFile(fullPath, content, 'utf8');
  }

  async fileExists(filePath) {
    const fullPath = path.join(this.baseDir, filePath);
    try {
      await fs.access(fullPath);
      return true;
    } catch {
      return false;
    }
  }

  async deleteFile(filePath) {
    const fullPath = path.join(this.baseDir, filePath);
    return fs.unlink(fullPath);
  }

  getFullPath(filePath) {
    return path.join(this.baseDir, filePath);
  }
}

module.exports = FileManager;