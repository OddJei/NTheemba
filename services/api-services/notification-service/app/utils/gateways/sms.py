from app.config.settings import settings
import httpx
import grpc
import os
import json
import logging
from app.utils.grpc_helpers import load_notifier_proto_runtime

logger = logging.getLogger("notification.notifier")


async def send_sms(notification):
    """Async SMS sender: try gRPC -> HTTP -> mock."""
    try:
        to = notification.payload.get("phone") if notification.payload else None
    except Exception:
        to = None

    # Defensive short-circuit: if the runtime toggle disables notifier, do not
    # perform any outbound calls. Prefer process env override so tests can
    # toggle behavior at runtime.
    env_val = os.getenv("NOTIFIER_ENABLED")
    notifier_enabled = None
    if env_val is not None:
        notifier_enabled = env_val.lower() in ("1", "true", "yes")
    else:
        notifier_enabled = getattr(settings, "NOTIFIER_ENABLED", True)

    if not notifier_enabled:
        try:
            logger.info("NOTIFIER_DISABLED: %s", json.dumps({
                "notification_id": getattr(notification, "id", None),
                "user_id": getattr(notification, "user_id", None),
                "channel": getattr(notification, "channel", None),
                "payload": getattr(notification, "payload", None),
                "AUDIT_ENABLED": getattr(settings, "AUDIT_ENABLED", True),
            }))
        except Exception:
            logger.info("NOTIFIER_DISABLED: (could not serialize notification)")
        return True, None

    if not to:
        return False, "missing phone number"

    gateway = settings.SMS_GATEWAY_URL
    if not gateway:
        # local mock behavior
        logger.info("MOCK_SMS: %s", json.dumps({"to": to, "message": notification.payload.get('message')}))
        return True, None

    grpc_target = getattr(settings, "NOTIFIER_GRPC_TARGET", None)
    if grpc_target:
        repo_proto = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), '..', '..', 'getways', 'notification getway', 'notifier', 'proto', 'notifier.proto')
        proto_path = os.path.normpath(repo_proto)
        if os.path.exists(proto_path):
            try:
                pb2, pb2_grpc = load_notifier_proto_runtime(proto_path)
                import grpc.aio

                async with grpc.aio.insecure_channel(grpc_target) as channel:
                    stub = pb2_grpc.NotifierStub(channel)
                    req = pb2.SMSRequest(to=to, message=notification.payload.get('message'))
                    resp = await stub.SendSMS(req)
                    return resp.ok, resp.error if resp.error else None
            except Exception as exc:
                logger.warning("gRPC SMS call failed, falling back to HTTP: %s", str(exc), exc_info=True)

    url = gateway.rstrip("/") + "/notify/sms"
    body = {"to": to, "message": notification.payload.get("message")}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, timeout=5.0)
        if resp.status_code == 200:
            return True, None
        return False, f"gateway_error:{resp.status_code}"
    except Exception as exc:
        return False, str(exc)
