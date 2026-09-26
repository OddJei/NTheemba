"""Tests for style-only local-language reply localization."""

from __future__ import annotations

from ntheemba.application.workflow_router import WorkflowReply
from ntheemba.services.reply_localization import (
    ReplyLocalizationConfig,
    SafeReplyLocalizer,
    protected_terms_for,
)


class StubReplyProvider:
    def __init__(self, text: str | Exception) -> None:
        self.text = text
        self.calls: list[dict[str, object]] = []

    async def propose_text(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


def test_protected_terms_include_prices_ids_dates_numbers_and_commands() -> None:
    terms = protected_terms_for(
        "Review your order request:\n"
        "Product: Anjoy Flavoured Drink\n"
        "Quantity: 1\n"
        "Unit price: K1.00\n"
        "Date: 20 Sep 2026\n"
        "Contact: +260000000015\n"
        "Reply CONFIRM to submit, CORRECT to change something, or CANCEL."
    )

    assert "Anjoy Flavoured Drink" in terms
    assert "K1.00" in terms
    assert "20 Sep 2026" in terms
    assert "+260000000015" in terms
    assert "CONFIRM" in terms


async def test_localizer_accepts_safe_local_language_rewrite() -> None:
    provider = StubReplyProvider(
        "Mwaiseni. Products found:\n"
        "1. Anjoy Flavoured Drink - K1.00 (available)\n"
        "Reply with the item number to continue. Zikomo."
    )
    localizer = SafeReplyLocalizer(
        provider=provider,
        config=ReplyLocalizationConfig(
            enabled=True,
            blend=0.15,
            languages=("bemba", "nyanja"),
        ),
    )
    reply = WorkflowReply.text_reply(
        "Products found:\n"
        "1. Anjoy Flavoured Drink - K1.00 (available)\n"
        "Reply with the item number to continue.",
        metadata={"response_type": "product_results"},
    )

    localized = await localizer.localize(reply)

    assert localized.text == provider.text
    assert localized.metadata == reply.metadata
    assert provider.calls[0]["blend"] == 0.15
    assert provider.calls[0]["languages"] == ("bemba", "nyanja")


async def test_localizer_falls_back_when_protected_fact_changes() -> None:
    provider = StubReplyProvider(
        "Products found:\n"
        "1. Anjoy Flavoured Drink - K2.00 (available)\n"
        "Reply with the item number to continue."
    )
    localizer = SafeReplyLocalizer(
        provider=provider,
        config=ReplyLocalizationConfig(enabled=True),
    )
    reply = WorkflowReply.text_reply(
        "Products found:\n"
        "1. Anjoy Flavoured Drink - K1.00 (available)\n"
        "Reply with the item number to continue.",
        metadata={"response_type": "product_results"},
    )

    localized = await localizer.localize(reply)

    assert localized is reply


async def test_localizer_skips_high_risk_order_submission_reply() -> None:
    provider = StubReplyProvider("Natotela, your order was submitted.")
    localizer = SafeReplyLocalizer(
        provider=provider,
        config=ReplyLocalizationConfig(enabled=True),
    )
    reply = WorkflowReply.text_reply(
        "Your order request TF-ORDER-1240 has been submitted. "
        "The business will confirm it. No payment has been taken.",
        metadata={"response_type": "order_submitted"},
    )

    localized = await localizer.localize(reply)

    assert localized is reply
    assert provider.calls == []


async def test_localizer_falls_back_when_provider_fails() -> None:
    provider = StubReplyProvider(RuntimeError("remote unavailable"))
    localizer = SafeReplyLocalizer(
        provider=provider,
        config=ReplyLocalizationConfig(enabled=True),
    )
    reply = WorkflowReply.text_reply(
        "I could not find a public product matching that.",
        metadata={"response_type": "catalogue_no_match"},
    )

    localized = await localizer.localize(reply)

    assert localized is reply
