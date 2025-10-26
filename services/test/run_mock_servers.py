#!/usr/bin/env python3
"""
Mock Servers Runner
Starts both SMS and Payment mock servers for development and testing.
"""
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

ROOT = Path(__file__).parent
SMS_SERVER = ROOT / "mock-servers" / "sms_mock_server.py"
PAYMENT_SERVER = ROOT / "mock-servers" / "payment_mock_server.py"

def start_server(script_path, name, port):
    """Start a mock server process."""
    print(f"🚀 Starting {name} on port {port}...")
    try:
        process = subprocess.Popen([
            sys.executable, str(script_path)
        ], cwd=str(ROOT))
        return process
    except Exception as e:
        print(f"❌ Failed to start {name}: {e}")
        return None

def main():
    """Start both mock servers."""
    print("🎭 Starting NTheemba Mock Servers")
    print("=" * 40)

    # Check if server files exist
    if not SMS_SERVER.exists():
        print(f"❌ SMS server not found: {SMS_SERVER}")
        return 1

    if not PAYMENT_SERVER.exists():
        print(f"❌ Payment server not found: {PAYMENT_SERVER}")
        return 1

    # Start servers
    sms_process = start_server(SMS_SERVER, "SMS Mock Server", 5101)
    payment_process = start_server(PAYMENT_SERVER, "Payment Mock Server", 5102)

    if not sms_process or not payment_process:
        print("❌ Failed to start one or more servers")
        return 1

    print("\n✅ Both mock servers started successfully!")
    print("📱 SMS Mock Server: http://localhost:5101")
    print("💰 Payment Mock Server: http://localhost:5102")
    print("\n📋 Available endpoints:")
    print("  SMS: /health, /api/v1/messages, /api/v1/verify, /logs")
    print("  Payment: /health, /api/v1/payments/initiate, /stats, /logs")
    print("\n🛑 Press Ctrl+C to stop all servers")

    def signal_handler(sig, frame):
        print("\n🛑 Stopping mock servers...")
        sms_process.terminate()
        payment_process.terminate()
        sms_process.wait()
        payment_process.wait()
        print("✅ All servers stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep running
    try:
        while True:
            time.sleep(1)
            # Check if processes are still running
            if sms_process.poll() is not None:
                print("❌ SMS server stopped unexpectedly")
                break
            if payment_process.poll() is not None:
                print("❌ Payment server stopped unexpectedly")
                break
    except KeyboardInterrupt:
        signal_handler(None, None)

    return 0

if __name__ == "__main__":
    sys.exit(main())