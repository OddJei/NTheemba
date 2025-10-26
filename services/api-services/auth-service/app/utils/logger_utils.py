import logging, json

logger = logging.getLogger("auth_service")
logger.setLevel(logging.INFO)

def log_event(event_type: str, data: dict):
    logger.info(json.dumps({"event": event_type, **data}))
