import pytest
from datetime import datetime, timedelta, timezone

from src.app.jobs.subscription_reminder import compute_reminder_actions, BizSnapshot, ReminderRecord
from src.app.main import _expires_at_from_exp_ts


def test_compute_reminder_actions_reminder_sequence():
    now = datetime(2025, 1, 8, tzinfo=timezone.utc)
    expiry = datetime(2025, 1, 15, tzinfo=timezone.utc)
    biz = BizSnapshot(id="b1", owner_id="u1", subscription_expiry=expiry, subscription_plan="paid", is_active=True)
    rec = ReminderRecord(business_id=biz.id)

    actions = compute_reminder_actions(biz, rec, now=now)
    # With REMINDER_DAYS = [7,3,1] and now 7 days before expiry, first reminder should be sent
    assert "send_reminder_1" in actions
    assert rec.reminders_sent == 1

    # Move forward to 3 days before expiry
    now2 = expiry - timedelta(days=3)
    actions2 = compute_reminder_actions(biz, rec, now=now2)
    assert "send_reminder_2" in actions2
    assert rec.reminders_sent == 2

    # At expiry day -> attempt_auto_pay (when not yet attempted)
    now3 = expiry
    actions3 = compute_reminder_actions(biz, rec, now=now3)
    assert "attempt_auto_pay" in actions3


def test_compute_reminder_actions_non_paid_or_inactive():
    now = datetime.now(timezone.utc)
    biz_free = BizSnapshot(id="b2", owner_id=None, subscription_expiry=now + timedelta(days=10), subscription_plan="free", is_active=True)
    rec_free = ReminderRecord(business_id=biz_free.id)
    assert compute_reminder_actions(biz_free, rec_free, now=now) == []

    biz_inactive = BizSnapshot(id="b3", owner_id=None, subscription_expiry=now + timedelta(days=10), subscription_plan="paid", is_active=False)
    rec_inactive = ReminderRecord(business_id=biz_inactive.id)
    assert compute_reminder_actions(biz_inactive, rec_inactive, now=now) == []


def test_expires_at_from_exp_ts_with_various_inputs():
    # integer
    dt = _expires_at_from_exp_ts(1700000000)
    assert isinstance(dt, datetime)

    # string number
    dt2 = _expires_at_from_exp_ts("1700000000")
    assert isinstance(dt2, datetime)

    # float-like string
    dt3 = _expires_at_from_exp_ts("1700000000.0")
    assert isinstance(dt3, datetime)

    # invalid -> raises HTTPException
    with pytest.raises(Exception):
        _expires_at_from_exp_ts(None)

    with pytest.raises(Exception):
        _expires_at_from_exp_ts("not-a-number")
