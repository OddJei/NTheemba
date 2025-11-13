from typing import Optional
import json
from pydantic import ValidationError

from ..models.messages import InboundMessage
from ..services.errors import PayloadValidationError
from ..services.session_manager import SessionManager


async def validate_and_check(raw: dict, session_manager: SessionManager) -> Optional[InboundMessage]:
    """Validate inbound envelope and perform idempotency check.

    Returns an InboundMessage on first-seen, or None if duplicate (already processed).
    Raises PayloadValidationError for structural validation errors.
    """
    try:
        inbound = InboundMessage.parse_obj(raw)
    except ValidationError as exc:
        raise PayloadValidationError(str(exc))

    # Idempotency check: ensure first processing
    first = await session_manager.ensure_first_processing(inbound.request_id)
    if not first:
        # duplicate
        return None

    return inbound
