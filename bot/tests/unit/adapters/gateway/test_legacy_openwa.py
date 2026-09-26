"""Tests for the legacy OpenWA envelope translator."""

from ntheemba.adapters.gateway import LegacyOpenWAEnvelopeAdapter, LegacyOpenWASession


def test_legacy_payload_uses_registered_channel_not_payload_business_id() -> None:
    adapter = LegacyOpenWAEnvelopeAdapter(
        (
            LegacyOpenWASession(
                legacy_session_id="serahs-glow-lounge-260976078440",
                channel_instance_id="wa-serahs-001",
                recipient_phone="+260976078440",
            ),
        )
    )

    message = adapter.convert_inbound(
        {
            "session_id": "serahs-glow-lounge-260976078440",
            "business_id": "harvest-big-shop",
            "message_id": "wamid-1",
            "from": "260970000101@c.us",
            "message": "I want to book",
        }
    )

    assert message.channel_instance_id == "wa-serahs-001"
    assert message.customer_phone == "+260970000101"
    assert message.metadata["legacy_business_id_ignored"] == "harvest-big-shop"
