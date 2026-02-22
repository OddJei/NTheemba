import pytest
from pydantic import ValidationError

from src.app import schemas


def test_botcreate_valid():
    b = schemas.BotCreate(phone_number='+260971234567', type='custom')
    assert b.phone_number.startswith('+260')


def test_botcreate_invalid_phone():
    with pytest.raises(ValidationError):
        schemas.BotCreate(phone_number='')


def test_create_session_requires_user_phone():
    with pytest.raises(ValidationError):
        schemas.CreateSessionReq(bot_id='bot1')


def test_create_event_requires_type_and_session():
    with pytest.raises(ValidationError):
        schemas.CreateEventReq(session_id='', event_type='')
