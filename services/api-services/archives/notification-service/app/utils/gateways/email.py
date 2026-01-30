from app.config.settings import settings
import httpx
import os
import json
import logging
from app.utils.grpc_helpers import load_notifier_proto_runtime

logger = logging.getLogger("notification.notifier")


async def send_email(notification):
    """Async email sender: prefer gRPC -> HTTP -> mock.

    Returns (ok: bool, error: Optional[str]).
    """
    try:
        to = notification.payload.get("email") if notification.payload else None
    except Exception:
        to = None

    if not to:
        return False, "missing email address"

    # Defensive short-circuit for runtime toggle. Prefer process env override
    # so tests can toggle behavior at runtime.
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

    gateway = settings.EMAIL_GATEWAY_URL
    if not gateway:
        try:
            logger.info("MOCK_EMAIL: %s", json.dumps({
                "to": to,
                "subject": notification.payload.get('subject'),
                "message": notification.payload.get('message'),
            }))
        except Exception:
            logger.info("MOCK_EMAIL: To=%s Subject=%s", to, notification.payload.get('subject'))
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
                    req = pb2.EmailRequest(to=to, subject=notification.payload.get('subject', ''), message=notification.payload.get('message', ''), html=notification.payload.get('html', ''))
                    resp = await stub.SendEmail(req)
                    return resp.ok, resp.error if resp.error else None
            except Exception as exc:
                logger.warning("gRPC Email call failed, falling back to HTTP: %s", str(exc), exc_info=True)

    url = gateway.rstrip("/") + "/notify/email"
    body = {"to": to, "subject": notification.payload.get("subject", ""), "message": notification.payload.get("message", "")}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, timeout=5.0)
        if resp.status_code == 200:
            return True, None
        return False, f"gateway_error:{resp.status_code}"
    except Exception as exc:
        return False, str(exc)
    
