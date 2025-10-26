"""Wrapper to run existing sms_mock_server Flask app on port 5000.

This avoids changing the original mock implementation and provides a
convenient entrypoint the test suite expects at http://localhost:5000.
"""
import os
import sys

# Ensure package imports work relative to this file
ROOT = os.path.dirname(__file__)
sys.path.insert(0, ROOT)

from sms_mock_server import app

if __name__ == '__main__':
    print("Starting SMS mock (wrapped) on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
