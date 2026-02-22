"""Demo script to exercise `app.helpers.service_helpers` against a running bot-session service.

Usage:
    python services/frontend/bot-services/ICE-service/scripts/demo_service_helpers.py

Requires a running bot-session service at BOT_SESSION_URL (default http://bot-session:8540).
"""
import asyncio
import os
import sys
import logging
from pathlib import Path

# Ensure both the ICE-service package dir and repository root are on sys.path
# so `app` and shared packages like `libs` resolve regardless of cwd.
ICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ICE_DIR))
sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger("demo_service_helpers")
logger.debug("sys.path for demo: %s", sys.path)
logger.info("REPO_ROOT=%s", REPO_ROOT)
logger.info("repo_root/libs exists: %s", REPO_ROOT.joinpath("libs").exists())

try:
    from app.helpers import service_helpers
except Exception as e:
    logger.exception("Failed to import app.helpers.service_helpers. sys.path=%s", sys.path)
    raise


logger = logging.getLogger("demo_service_helpers")
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")


async def main():
    token = os.getenv("DEMO_BOT_SESSION_TOKEN")
    auth_headers = None
    if token:
        auth_headers = {"Authorization": f"Bearer {token}"}

    logger.info("Demo: create bot (auth_headers=%s)", bool(auth_headers))
    try:
        bot = await service_helpers.create_bot(
            "+260772000001",
            name="ICE Demo Bot",
            business_id=os.getenv("DEMO_BUSINESS_ID", "biz-demo"),
            auth_headers=auth_headers,
        )
        logger.info("bot -> %s", bot)
    except Exception:
        logger.exception("create_bot failed")

    phone = "+260772000002"
    logger.info("Demo: get bot by phone -> %s", phone)
    try:
        found = await service_helpers.get_bot_by_phone(phone, auth_headers=auth_headers)
        logger.info("found -> %s", found)
    except Exception:
        logger.exception("get_bot_by_phone failed")

    logger.info("Demo: create user-bot session")
    try:
        session = await service_helpers.create_user_bot_session(
            phone,
            os.getenv("DEMO_BUSINESS_ID", "biz-demo"),
            {"platform": "whatsapp"},
            auth_headers=auth_headers,
        )
        logger.info("session -> %s", session)
    except Exception:
        logger.exception("create_user_bot_session failed")
        session = {}

    if session and session.get("session_id"):
        sid = session["session_id"]
        logger.info("Setting session state to 'cart' for %s", sid)
        try:
            ok = await service_helpers.create_session_state(sid, "cart", {"cart_items": []}, auth_headers=auth_headers)
            logger.info("create_session_state -> %s", ok)
        except Exception:
            logger.exception("create_session_state failed")

        logger.info("Upgrade cycle state to 'order' for %s", sid)
        try:
            cycle = await service_helpers.upgrade_cycle_state(sid, "order", metadata={"entry": "demo"}, auth_headers=auth_headers)
            logger.info("upgrade_cycle_state -> %s", cycle)
        except Exception:
            logger.exception("upgrade_cycle_state failed")

        logger.info("Closing session %s", sid)
        try:
            closed = await service_helpers.close_user_bot_session(sid, reason="demo_complete", auth_headers=auth_headers)
            logger.info("closed -> %s", closed)
        except Exception:
            logger.exception("close_user_bot_session failed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("Demo script failed")
