// General utility functions

const generateId = () => {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
};

const isValidPhoneNumber = (phone) => {
  // E.164 format validation
  const phoneRegex = /^\+[1-9]\d{1,14}$/;
  return phoneRegex.test(phone);
};

const sanitizeString = (str) => {
  return str ? str.toString().trim() : '';
};

const delay = (ms) => {
  return new Promise(resolve => setTimeout(resolve, ms));
};

module.exports = {
  generateId,
  isValidPhoneNumber,
  sanitizeString,
  delay
};