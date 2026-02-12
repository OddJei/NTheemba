"""Entrypoint for custom-bot-service."""

from services.session_service import SessionServiceClient
from utils.payload_validator import is_valid_payload


def run_demo():
    svc = SessionServiceClient(base_url="http://localhost:8000")
    payload = {"type": "message", "data": {"text": "hello from custom"}}
    print("payload valid:", is_valid_payload(payload))
    print("start session:", svc.start_session(user_id="user123"))


if __name__ == "__main__":
    run_demo()
