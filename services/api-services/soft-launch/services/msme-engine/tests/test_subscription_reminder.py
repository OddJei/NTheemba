from datetime import datetime, timedelta, timezone
import pytest

from src.app.jobs.subscription_reminder import BizSnapshot, ReminderRecord, compute_reminder_actions


def make_biz(days_until_expiry: int, is_active: bool = True) -> BizSnapshot:
    return BizSnapshot(
        id="biz-1",
        owner_id="user-1",
        subscription_expiry=datetime.now(timezone.utc) + timedelta(days=days_until_expiry),
        subscription_plan="paid",
        is_active=is_active,
    )


def test_send_three_reminders_spaced():
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=7)
    biz = BizSnapshot(id="b1", owner_id="u1", subscription_expiry=expiry, subscription_plan="paid", is_active=True)
    record = ReminderRecord(business_id=biz.id)

    # simulate at exactly 7 days before expiry -> reminder 1
    t1 = expiry - timedelta(days=7)
    actions = compute_reminder_actions(biz, record, now=t1)
    assert "send_reminder_1" in actions
    assert record.reminders_sent == 1

    # simulate at 3 days before expiry -> reminder 2
    t2 = expiry - timedelta(days=3)
    actions = compute_reminder_actions(biz, record, now=t2)
    assert "send_reminder_2" in actions
    assert record.reminders_sent == 2

    # simulate at 1 day before expiry -> reminder 3
    t3 = expiry - timedelta(days=1)
    actions = compute_reminder_actions(biz, record, now=t3)
    assert "send_reminder_3" in actions
    assert record.reminders_sent == 3


def test_attempt_auto_pay_and_expire():
    now = datetime.now(timezone.utc)
    expiry = now - timedelta(seconds=1)  # already expired
    biz = BizSnapshot(id="b2", owner_id="u2", subscription_expiry=expiry, subscription_plan="paid", is_active=True)
    record = ReminderRecord(business_id=biz.id)

    # first compute: should attempt auto pay
    actions = compute_reminder_actions(biz, record, now=now)
    assert "attempt_auto_pay" in actions
    # mark attempted and recompute to simulate failure
    record.auto_pay_attempted = True
    actions = compute_reminder_actions(biz, record, now=now)
    assert "expire_account" in actions


def test_no_actions_for_free_or_inactive():
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=5)
    biz_free = BizSnapshot(id="b3", owner_id="u3", subscription_expiry=expiry, subscription_plan="free", is_active=True)
    record = ReminderRecord(business_id=biz_free.id)
    actions = compute_reminder_actions(biz_free, record, now=now)
    assert actions == []

    biz_inactive = BizSnapshot(id="b4", owner_id="u4", subscription_expiry=expiry, subscription_plan="paid", is_active=False)
    record2 = ReminderRecord(business_id=biz_inactive.id)
    actions = compute_reminder_actions(biz_inactive, record2, now=now)
    assert actions == []
