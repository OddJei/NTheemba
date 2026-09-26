"""Stable enum values used throughout the Ntheemba domain."""

from enum import StrEnum


class ConversationMode(StrEnum):
    BOT = "bot"
    HUMAN = "human"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    EXPIRED = "expired"


class Flow(StrEnum):
    IDLE = "idle"
    INFORMATION = "information"
    FAQ = "faq"
    CATALOGUE = "catalogue"
    ORDER = "order"
    BOOKING = "booking"
    HANDOVER = "handover"


class Stage(StrEnum):
    START = "start"
    INFORMATION_LOOKUP = "information_lookup"
    FAQ_SEARCH = "faq_search"
    CATALOGUE_SEARCH = "catalogue_search"
    ITEM_SELECTION = "item_selection"
    PRODUCT_CLARIFICATION = "product_clarification"
    PRODUCT_SELECTED = "product_selected"
    QUANTITY = "quantity"
    FULFILMENT_METHOD = "fulfilment_method"
    DELIVERY_DETAILS = "delivery_details"
    SERVICE_SELECTION = "service_selection"
    PREFERRED_DATE = "preferred_date"
    TIME_SELECTION = "time_selection"
    STAFF_SELECTION = "staff_selection"
    CUSTOMER_DETAILS = "customer_details"
    ORDER_REVIEW = "order_review"
    BOOKING_REVIEW = "booking_review"
    CUSTOMER_CONFIRMATION = "customer_confirmation"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"
    WAITING_FOR_HUMAN = "waiting_for_human"
    HUMAN_ACTIVE = "human_active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IntentType(StrEnum):
    BUSINESS_INFO = "business_info"
    BUSINESS_HOURS = "business_hours"
    FAQ = "faq"
    LOYALTY_STATUS = "loyalty_status"
    CATALOGUE_SEARCH = "catalogue_search"
    SELECT_ITEM = "select_item"
    START_ORDER = "start_order"
    START_BOOKING = "start_booking"
    PROVIDE_QUANTITY = "provide_quantity"
    PROVIDE_FULFILMENT_METHOD = "provide_fulfilment_method"
    PROVIDE_DELIVERY_DETAILS = "provide_delivery_details"
    PROVIDE_DATE = "provide_date"
    SELECT_TIME = "select_time"
    SELECT_STAFF = "select_staff"
    PROVIDE_CUSTOMER_DETAILS = "provide_customer_details"
    CONFIRM = "confirm"
    CORRECT = "correct"
    CANCEL = "cancel"
    HANDOVER = "handover"
    RESUME_BOT = "resume_bot"
    CLOSE_SESSION = "close_session"
    CONTINUE = "continue"
    CLARIFY = "clarify"
    UNKNOWN = "unknown"


class MessageRole(StrEnum):
    SYSTEM_COMMAND = "system_command"
    GLOBAL_COMMAND = "global_command"
    PENDING_ANSWER = "pending_answer"
    SAFE_INTERRUPTION = "safe_interruption"
    NEW_REQUEST = "new_request"
    UNKNOWN = "unknown"


class ProductResolutionStatus(StrEnum):
    NOT_STARTED = "not_started"
    NO_MATCH = "no_match"
    ONE_MATCH = "one_match"
    SUGGEST_CONFIRMATION = "suggest_confirmation"
    NEEDS_CLARIFICATION = "needs_clarification"
    RESOLVED = "resolved"


class ProductResolutionOutcome(StrEnum):
    NCPC_NO_MATCH = "NCPC_NO_MATCH"
    SHOP_NO_MATCH = "SHOP_NO_MATCH"
    SHOP_MATCHES = "SHOP_MATCHES"
    NCPC_TIMEOUT = "NCPC_TIMEOUT"
    TRADEFLOW_TIMEOUT = "TRADEFLOW_TIMEOUT"
    AUTH_FAILURE = "AUTH_FAILURE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    STALE_SELECTION = "STALE_SELECTION"
    SESSION_EXPIRED = "SESSION_EXPIRED"


class HandoverStatus(StrEnum):
    NONE = "none"
    REQUESTED = "requested"
    WAITING = "waiting"
    ACTIVE = "active"
    RESOLVED = "resolved"


class FulfilmentMethod(StrEnum):
    COLLECTION = "collection"
    DELIVERY = "delivery"


class ItemType(StrEnum):
    PRODUCT = "product"
    SERVICE = "service"


class RelativeSize(StrEnum):
    SMALLEST = "smallest"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    LARGEST = "largest"
