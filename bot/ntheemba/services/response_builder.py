"""Customer-safe response construction for all Ntheemba workflows."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType
from typing import Final

from ntheemba.application.workflow_router import WorkflowReply
from ntheemba.domain.booking_draft import AppointmentSlot, BookingDraft, ServiceSelection
from ntheemba.domain.enums import Flow, FulfilmentMethod, ProductResolutionOutcome
from ntheemba.domain.order_draft import OrderDraft
from ntheemba.domain.product_resolution import ProductCandidate, ProductResolution
from ntheemba.ports.tradeflow import (
    BusinessHours,
    BusinessInformation,
    BusinessProduct,
    FAQAnswer,
    ProductAvailability,
    StaffOption,
    SubmissionResult,
)

_CONTROL_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[ \t]+")


class ResponseBuilderError(ValueError):
    """Raised when approved data is insufficient to build a safe response."""


@dataclass(frozen=True, slots=True)
class ResponseBuilderConfig:
    """Formatting and length limits for customer-facing replies."""

    currency_symbols: Mapping[str, str] = field(
        default_factory=lambda: {
            "ZMW": "K",
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "ZAR": "R",
        }
    )
    max_catalogue_items: int = 10
    max_text_length: int = 3500
    date_format: str = "%d %b %Y"
    time_format: str = "%H:%M"

    def __post_init__(self) -> None:
        if self.max_catalogue_items <= 0:
            raise ValueError("max_catalogue_items must be greater than zero")
        if self.max_text_length < 200:
            raise ValueError("max_text_length must be at least 200 characters")
        symbols = {
            str(currency).strip().upper(): str(symbol)
            for currency, symbol in self.currency_symbols.items()
            if str(currency).strip()
        }
        object.__setattr__(self, "currency_symbols", MappingProxyType(symbols))


class ResponseBuilder:
    """Turn approved domain and port data into consistent workflow replies.

    The builder performs no I/O and never mutates sessions or workflow drafts.
    It deliberately receives only customer-safe DTOs and typed domain objects.
    """

    def __init__(self, config: ResponseBuilderConfig | None = None) -> None:
        self.config = config or ResponseBuilderConfig()

    def business_information(self, info: BusinessInformation) -> WorkflowReply:
        """Build a concise public business profile."""

        lines = [info.name]
        if info.description:
            lines.append(self._clean(info.description))
        if info.location:
            lines.append(f"Location: {self._clean(info.location)}")
        if info.contact_phone:
            lines.append(f"Contact: {self._clean(info.contact_phone)}")
        return self._text("\n".join(lines), response_type="business_information")

    def business_hours(self, hours: BusinessHours) -> WorkflowReply:
        """Explain opening status without exposing internal schedules."""

        date_label = self._format_date(hours.local_date)
        note = self._clean(hours.note) if hours.note else ""

        if hours.special_closure:
            text = f"The business is closed on {date_label}."
            if note:
                text += f" {note}"
            return self._text(text, response_type="business_hours")

        if hours.opens_at is None or hours.closes_at is None:
            status = "open" if hours.is_open else "closed"
            text = f"The business is currently {status}."
            if note:
                text += f" {note}"
            return self._text(text, response_type="business_hours")

        opens = self._format_time(hours.opens_at)
        closes = self._format_time(hours.closes_at)
        if hours.is_open:
            text = f"Yes, the business is open now and closes at {closes}."
        else:
            text = f"The business is currently closed. Hours for {date_label}: {opens}-{closes}."
        if note:
            text += f" {note}"
        return self._text(text, response_type="business_hours")

    def faq_answer(self, answer: FAQAnswer) -> WorkflowReply:
        """Return one approved FAQ answer."""

        return self._text(self._clean(answer.answer), response_type="faq_answer")

    def faq_not_found(self) -> WorkflowReply:
        """Ask for another wording when no approved FAQ matched."""

        return self._text(
            "I could not find an approved answer for that question. "
            "Please rephrase it or ask to speak with a person.",
            response_type="faq_not_found",
        )

    def product_results(
        self,
        products: Sequence[BusinessProduct],
        *,
        prompt: str = "Reply with the item number to continue.",
    ) -> WorkflowReply:
        """Build numbered business-product results."""

        visible = [product for product in products if product.public_visible]
        if not visible:
            return self.no_catalogue_match(item_name="product")

        rows: list[str] = []
        for index, product in enumerate(visible[: self.config.max_catalogue_items], start=1):
            availability = "available" if product.available else "currently unavailable"
            price = self.format_money(product.selling_price, product.currency)
            rows.append(f"{index}. {self._clean(product.name)} — {price} ({availability})")

        footer = self._clean(prompt)
        if len(visible) > self.config.max_catalogue_items:
            footer = f"Showing the first {self.config.max_catalogue_items} results. {footer}"
        return self._text(
            "Products found:\n" + "\n".join(rows) + f"\n{footer}",
            response_type="product_results",
            result_count=len(visible),
        )

    def service_results(
        self,
        services: Sequence[ServiceSelection],
        *,
        prompt: str = "Reply with the service number to continue.",
    ) -> WorkflowReply:
        """Build numbered service results."""

        if not services:
            return self.no_catalogue_match(item_name="service")

        rows: list[str] = []
        for index, service in enumerate(services[: self.config.max_catalogue_items], start=1):
            detail = f"{service.duration_minutes} minutes"
            if service.price is not None and service.currency is not None:
                detail += f", {self.format_money(service.price, service.currency)}"
            rows.append(f"{index}. {self._clean(service.name)} — {detail}")

        footer = self._clean(prompt)
        if len(services) > self.config.max_catalogue_items:
            footer = f"Showing the first {self.config.max_catalogue_items} results. {footer}"
        return self._text(
            "Services found:\n" + "\n".join(rows) + f"\n{footer}",
            response_type="service_results",
            result_count=len(services),
        )

    def no_catalogue_match(self, *, item_name: str) -> WorkflowReply:
        """Build a safe no-result response."""

        cleaned = self._clean(item_name) or "item"
        return self._text(
            f"I could not find a public {cleaned} matching that. "
            "Try another name, size, brand, or category.",
            response_type="catalogue_no_match",
        )

    def product_resolution_failure(self, outcome: ProductResolutionOutcome) -> WorkflowReply:
        """Build deterministic, customer-safe product-resolution failure replies."""

        messages = {
            ProductResolutionOutcome.NCPC_NO_MATCH: (
                "I could not find a public product matching that. "
                "Try another name, size, brand, or category, or ask for a person."
            ),
            ProductResolutionOutcome.SHOP_NO_MATCH: (
                "I could not find that product in this shop's public catalogue. "
                "Try another product or ask for a person."
            ),
            ProductResolutionOutcome.SHOP_MATCHES: (
                "I found more than one possible product. Please choose from the listed options."
            ),
            ProductResolutionOutcome.NCPC_TIMEOUT: (
                "I could not check the product catalogue right now. "
                "Please try again shortly or ask for a person."
            ),
            ProductResolutionOutcome.TRADEFLOW_TIMEOUT: (
                "I could not check this shop's product details right now. "
                "Please try again shortly or ask for a person."
            ),
            ProductResolutionOutcome.AUTH_FAILURE: (
                "I cannot access the product information for this shop right now. "
                "Please ask for a person."
            ),
            ProductResolutionOutcome.MALFORMED_RESPONSE: (
                "I could not read the product information safely. Please ask for a person."
            ),
            ProductResolutionOutcome.STALE_SELECTION: (
                "Those product choices are no longer active. Please search for the product again."
            ),
            ProductResolutionOutcome.SESSION_EXPIRED: (
                "Your previous session expired. Please send the product request again."
            ),
        }
        return self._text(
            messages[outcome],
            response_type="product_resolution_failure",
            outcome=outcome.value,
        )

    def product_detail(self, product: BusinessProduct) -> tuple[WorkflowReply, ...]:
        """Build product details, optionally including a public image."""

        availability = "Available" if product.available else "Currently unavailable"
        caption = (
            f"{self._clean(product.name)}\n"
            f"Price: {self.format_money(product.selling_price, product.currency)}\n"
            f"Status: {availability}"
        )
        text_reply = self._text(
            caption
            + (
                '\nYou can say "order this" to continue.'
                if product.available
                else "\nYou can choose another product."
            ),
            response_type="product_detail",
        )
        if not product.image_url:
            return (text_reply,)
        image_reply = WorkflowReply.image_reply(
            self._clean_url(product.image_url),
            caption=caption,
            metadata={"response_type": "product_image"},
        )
        return (image_reply, text_reply)

    def service_detail(self, service: ServiceSelection) -> WorkflowReply:
        """Build customer-visible service details."""

        lines = [self._clean(service.name), f"Duration: {service.duration_minutes} minutes"]
        if service.price is not None and service.currency is not None:
            lines.append(f"Price: {self.format_money(service.price, service.currency)}")
        lines.append('You can say "book this" to continue.')
        return self._text("\n".join(lines), response_type="service_detail")

    def product_clarification(self, resolution: ProductResolution) -> WorkflowReply:
        """Ask the customer to choose between controlled product candidates."""

        candidates = resolution.candidates
        if len(candidates) < 2:
            raise ResponseBuilderError("product clarification requires at least two candidates")

        options = resolution.clarification_options or tuple(
            self._candidate_label(candidate) for candidate in candidates
        )
        if len(options) < 2:
            raise ResponseBuilderError("product clarification requires at least two options")

        rows = [f"{index}. {self._clean(option)}" for index, option in enumerate(options, start=1)]
        return self._text(
            "I found more than one possible product:\n"
            + "\n".join(rows)
            + "\nWhich one would you like?",
            response_type="product_clarification",
            option_count=len(options),
        )

    def product_suggestion(
        self,
        candidate: ProductCandidate,
        *,
        reason: str = "This appears to be the closest match.",
    ) -> WorkflowReply:
        """Ask the customer to confirm a strong but non-final match."""

        return self._text(
            f"{self._clean(reason)} Is it {self._candidate_label(candidate)}? "
            "Reply YES to continue or tell me the correct size or variant.",
            response_type="product_suggestion",
        )

    def quantity_unavailable(self, availability: ProductAvailability) -> WorkflowReply:
        """Explain that the requested quantity cannot currently proceed."""

        if not availability.public_visible:
            return self._text(
                "That product is no longer available for customer orders. "
                "Please choose another product.",
                response_type="quantity_unavailable",
            )
        return self._text(
            f"That quantity is not available. Current available quantity: "
            f"{availability.available_quantity}. Enter a smaller quantity or cancel.",
            response_type="quantity_unavailable",
            available_quantity=availability.available_quantity,
        )

    def available_slots(self, slots: Sequence[AppointmentSlot]) -> WorkflowReply:
        """Build a numbered list of appointment slots."""

        if not slots:
            return self._text(
                "There are no available appointment times on that date. "
                "Please choose another date.",
                response_type="slots_unavailable",
            )
        rows = [
            f"{index}. {self._format_time(slot.start_time)}-{self._format_time(slot.end_time)}"
            + (f" with {self._clean(slot.staff_name)}" if slot.staff_name else "")
            for index, slot in enumerate(slots[: self.config.max_catalogue_items], start=1)
        ]
        return self._text(
            "Available times:\n" + "\n".join(rows) + "\nReply with the time number.",
            response_type="available_slots",
            result_count=len(slots),
        )

    def staff_options(
        self,
        staff: Sequence[StaffOption],
        *,
        allow_no_preference: bool = False,
    ) -> WorkflowReply:
        """Build a numbered list of qualified staff without exposing IDs."""

        if not staff:
            return self._text(
                "No specific staff options are available for that time. "
                "The business can assign an available qualified staff member.",
                response_type="staff_unavailable",
            )
        rows = [
            f"{index}. {self._clean(option.name)}"
            for index, option in enumerate(staff[: self.config.max_catalogue_items], start=1)
        ]
        instruction = "Reply with the staff number."
        if allow_no_preference:
            instruction = "Reply with the staff number, or SKIP for no preference."
        return self._text(
            "Available staff:\n" + "\n".join(rows) + f"\n{instruction}",
            response_type="staff_options",
            result_count=len(staff),
        )

    def order_review(self, draft: OrderDraft) -> WorkflowReply:
        """Build the final customer order review."""

        missing = draft.missing_fields()
        if missing:
            raise ResponseBuilderError(
                "order review requires complete draft fields: " + ", ".join(missing)
            )
        assert draft.product is not None
        assert draft.quantity is not None
        assert draft.fulfilment_method is not None
        assert draft.customer_name is not None
        assert draft.contact_number is not None

        lines = [
            "Review your order request:",
            f"Product: {self._clean(draft.product.name)}",
            f"Quantity: {draft.quantity}",
            f"Fulfilment: {draft.fulfilment_method.value}",
        ]
        if draft.fulfilment_method == FulfilmentMethod.DELIVERY:
            assert draft.delivery_details is not None
            lines.append(f"Delivery: {self._clean(draft.delivery_details)}")
        if draft.price_snapshot is not None:
            unit_price = self.format_money(
                draft.price_snapshot.amount,
                draft.price_snapshot.currency,
            )
            lines.append(f"Unit price: {unit_price}")
            if draft.total_price is not None:
                total_price = self.format_money(
                    draft.total_price,
                    draft.price_snapshot.currency,
                )
                lines.append(f"Estimated total: {total_price}")
        lines.extend(
            [
                f"Name: {self._clean(draft.customer_name)}",
                f"Contact: {self._clean(draft.contact_number)}",
                "Reply CONFIRM to submit, CORRECT to change something, or CANCEL.",
            ]
        )
        return self._text("\n".join(lines), response_type="order_review")

    def price_changed_order_review(
        self,
        draft: OrderDraft,
        *,
        previous_amount: Decimal | None,
        previous_currency: str | None,
    ) -> WorkflowReply:
        """Show a revised order review and require fresh confirmation."""

        review = self.order_review(draft)
        assert review.text is not None
        change = "The product price changed before submission."
        if previous_amount is not None and previous_currency is not None:
            previous = self.format_money(previous_amount, previous_currency)
            current = (
                self.format_money(
                    draft.price_snapshot.amount,
                    draft.price_snapshot.currency,
                )
                if draft.price_snapshot is not None
                else "the current price"
            )
            change = f"The unit price changed from {previous} to {current}."
        return self._text(
            f"{change} Please review the updated order.\n\n{review.text}",
            response_type="order_price_changed",
        )

    def booking_review(self, draft: BookingDraft) -> WorkflowReply:
        """Build the final customer booking review."""

        missing = draft.missing_fields()
        if missing:
            raise ResponseBuilderError(
                "booking review requires complete draft fields: " + ", ".join(missing)
            )
        assert draft.service is not None
        assert draft.selected_slot is not None
        assert draft.customer_name is not None
        assert draft.contact_number is not None

        slot = draft.selected_slot
        lines = [
            "Review your booking request:",
            f"Service: {self._clean(draft.service.name)}",
            f"Date: {self._format_date(slot.appointment_date)}",
            f"Time: {self._format_time(slot.start_time)}-{self._format_time(slot.end_time)}",
        ]
        if slot.staff_name:
            lines.append(f"Staff: {self._clean(slot.staff_name)}")
        if draft.service.price is not None and draft.service.currency is not None:
            lines.append(f"Price: {self.format_money(draft.service.price, draft.service.currency)}")
        lines.extend(
            [
                f"Name: {self._clean(draft.customer_name)}",
                f"Contact: {self._clean(draft.contact_number)}",
                "Reply CONFIRM to submit, CORRECT to change something, or CANCEL.",
            ]
        )
        return self._text("\n".join(lines), response_type="booking_review")

    def booking_price_changed_review(self, draft: BookingDraft) -> WorkflowReply:
        """Show updated booking details and require fresh confirmation."""

        review = self.booking_review(draft)
        assert review.text is not None
        return self._text(
            "The service details or price changed. Please review the updated booking.\n\n"
            + review.text,
            response_type="booking_price_changed",
        )

    def slot_no_longer_available(
        self,
        slots: Sequence[AppointmentSlot],
    ) -> WorkflowReply:
        """Explain that a selected slot changed and show current alternatives."""

        alternatives = self.available_slots(slots)
        assert alternatives.text is not None
        return self._text(
            "That appointment time is no longer available.\n" + alternatives.text,
            response_type="booking_slot_changed",
        )

    def staff_no_longer_available(
        self,
        staff: Sequence[StaffOption],
    ) -> WorkflowReply:
        """Explain that chosen staff changed and show current alternatives."""

        alternatives = self.staff_options(staff, allow_no_preference=True)
        assert alternatives.text is not None
        return self._text(
            "The selected staff member is no longer available for that time.\n" + alternatives.text,
            response_type="booking_staff_changed",
        )

    def order_submitted(self, result: SubmissionResult) -> WorkflowReply:
        """Confirm that an order request, not a payment, was submitted."""

        return self._text(
            f"Your order request {self._clean(result.request_id)} has been submitted. "
            "The business will confirm it. No payment has been taken.",
            response_type="order_submitted",
            created=result.created,
        )

    def booking_submitted(self, result: SubmissionResult) -> WorkflowReply:
        """Confirm that a booking request was submitted for business approval."""

        return self._text(
            f"Your booking request {self._clean(result.request_id)} has been submitted. "
            "The business will confirm it. No payment has been taken.",
            response_type="booking_submitted",
            created=result.created,
        )

    def ask_for_missing_order_field(self, field_name: str) -> WorkflowReply:
        """Ask only for the next missing order field."""

        prompts = {
            "product": "Which product would you like to order?",
            "quantity": "How many would you like?",
            "fulfilment_method": "Would you like collection or delivery?",
            "delivery_details": "Please send the delivery address and useful directions.",
            "customer_name": "Please send your name and contact number.",
            "contact_number": "Please send your name and contact number.",
        }
        return self._text(
            prompts.get(field_name, "Please provide the missing order information."),
            response_type="order_missing_field",
            field=field_name,
        )

    def ask_for_missing_booking_field(self, field_name: str) -> WorkflowReply:
        """Ask only for the next missing booking field."""

        prompts = {
            "service": "Which service would you like to book?",
            "preferred_date": "What date would you prefer? Please use YYYY-MM-DD.",
            "selected_slot": "Please choose one of the available time options.",
            "customer_name": "Please send your name and contact number.",
            "contact_number": "Please send your name and contact number.",
        }
        return self._text(
            prompts.get(field_name, "Please provide the missing booking information."),
            response_type="booking_missing_field",
            field=field_name,
        )

    def correction_prompt(self, flow: Flow, field_name: str) -> WorkflowReply:
        """Ask for one corrected workflow field."""

        order_prompts = {
            "product": "Choose the product again.",
            "quantity": "What quantity would you like instead?",
            "fulfilment_method": "Choose collection or delivery.",
            "delivery_details": "Send the corrected delivery details.",
            "customer_details": "Send the corrected name and contact number.",
        }
        booking_prompts = {
            "service": "Choose the service again.",
            "preferred_date": "Send the corrected date in YYYY-MM-DD format.",
            "selected_slot": "Choose another available time.",
            "staff": "Choose another listed staff option.",
            "customer_details": "Send the corrected name and contact number.",
        }
        prompts = order_prompts if flow == Flow.ORDER else booking_prompts
        return self._text(
            prompts.get(field_name, "Tell me what you would like to correct."),
            response_type="correction_prompt",
            field=field_name,
        )

    def clarification(self, prompt: str | None = None) -> WorkflowReply:
        """Ask a concise clarification question."""

        return self._text(
            prompt
            or "I did not understand that clearly. Please say what you would like to do, "
            "or ask to speak with a person.",
            response_type="clarification",
        )

    def cancelled(self) -> WorkflowReply:
        """Confirm cancellation of the active request."""

        return self._text(
            "The active request has been cancelled. What else can I help with?",
            response_type="cancelled",
        )

    def handover_requested(self) -> WorkflowReply:
        """Confirm that the conversation is waiting for a person."""

        return self._text(
            "I have paused automated replies and requested a person to assist you. "
            "Your conversation details have been kept.",
            response_type="handover_requested",
        )

    def human_active(self) -> WorkflowReply:
        """Tell the customer that a person is handling the conversation."""

        return self._text(
            "A person is now handling this conversation. Automated replies remain paused.",
            response_type="human_active",
        )

    def conversation_closed(self) -> WorkflowReply:
        """Confirm that the assisted conversation has ended."""

        return self._text(
            "This conversation has been closed. Send a new message whenever you need help again.",
            response_type="conversation_closed",
        )

    def bot_resumed(self, pending_prompt: str | None = None) -> WorkflowReply:
        """Confirm bot resumption and optionally repeat the pending question."""

        text = "Automated assistance has resumed."
        if pending_prompt:
            text += f" {self._clean(pending_prompt)}"
        return self._text(text, response_type="bot_resumed")

    def workflow_resumed(self, pending_prompt: str | None = None) -> WorkflowReply:
        """Return the customer to an interrupted workflow."""

        text = "We can continue with your previous request."
        if pending_prompt:
            text = f"Back to your previous request: {self._clean(pending_prompt)}"
        return self._text(text, response_type="workflow_resumed")

    def dependency_failure(
        self,
        *,
        retryable: bool,
        action_name: str = "that request",
    ) -> WorkflowReply:
        """Build a safe external-dependency failure response."""

        action = self._clean(action_name) or "that request"
        if retryable:
            text = (
                f"I could not complete {action} because a business service is temporarily "
                "unavailable. Please try again shortly or ask for a person."
            )
        else:
            text = (
                f"I could not complete {action}. Please check the details, try another option, "
                "or ask for a person."
            )
        return self._text(
            text,
            response_type="dependency_failure",
            retryable=retryable,
        )

    def generic_failure(self) -> WorkflowReply:
        """Build the standard unexpected-failure response."""

        return self._text(
            "I'm sorry, I could not complete that request. Please try again or ask for a person.",
            response_type="generic_failure",
        )

    def format_money(self, amount: Decimal, currency: str) -> str:
        """Format money consistently without floating-point conversion."""

        if amount < 0:
            raise ValueError("amount must not be negative")
        normalized_currency = currency.strip().upper()
        if len(normalized_currency) != 3:
            raise ValueError("currency must use a three-letter code")
        rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        symbol = self.config.currency_symbols.get(normalized_currency)
        if symbol is not None:
            return f"{symbol}{rounded:,.2f}"
        return f"{normalized_currency} {rounded:,.2f}"

    def _candidate_label(self, candidate: ProductCandidate) -> str:
        name = self._clean(candidate.name)
        if candidate.size_value is None or candidate.size_unit is None:
            return name
        size = self._decimal_label(candidate.size_value)
        size_token = f"{size}{candidate.size_unit}"
        if size_token.lower() in name.lower().replace(" ", ""):
            return name
        return f"{name} — {size_token}"

    @staticmethod
    def _decimal_label(value: Decimal) -> str:
        normalized = value.normalize()
        return format(normalized, "f")

    def _text(self, text: str, *, response_type: str, **metadata: object) -> WorkflowReply:
        cleaned = self._clean(text)
        if not cleaned:
            raise ResponseBuilderError("response text must not be empty")
        if len(cleaned) > self.config.max_text_length:
            cleaned = cleaned[: self.config.max_text_length - 1].rstrip() + "…"
        reply_metadata = {"response_type": response_type, **metadata}
        return WorkflowReply.text_reply(cleaned, metadata=reply_metadata)

    @staticmethod
    def _clean(value: str) -> str:
        stripped = _CONTROL_PATTERN.sub("", str(value)).strip()
        lines = [
            _WHITESPACE_PATTERN.sub(" ", line).strip()
            for line in stripped.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        ]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _clean_url(value: str) -> str:
        cleaned = ResponseBuilder._clean(value)
        if not cleaned.startswith(("https://", "http://")):
            raise ResponseBuilderError("public image URL must use HTTP or HTTPS")
        return cleaned

    def _format_date(self, value: date) -> str:
        return value.strftime(self.config.date_format)

    def _format_time(self, value: time) -> str:
        return value.strftime(self.config.time_format)
