# Stage Spec (Runtime)

## Overview
- Goal: drive stage-aware intent resolution and multi-slot questioning.
- Product matching rule: when a product snapshot is provided with ids, Gemini MUST return `product_id` for any product-related intent (names are allowed as extra metadata but `product_id` is required for execution).

## Stage Spec Table

| Stage | Canonical Intents | Required Slots (Ask Together) | Optional Slots | Notes |
| --- | --- | --- | --- | --- |
| chat | greet_and_suggest, help, browse_catalogue, view_cart, add_item, remove_item, clear_cart, cancel | none (multi-slot: allow up to 3 product picks) | product_id(s), product_name(s) | If unclear, return greet_and_suggest. If snapshot provided, return product_id(s). |
| cart | browse_catalogue, select_product, inspect_item, add_item, remove_item, view_cart, clear_cart, help, cancel | product_id or product_name (ask up to 3 items in one turn) | quantity, category_id | Allow up to 5 product picks if snapshot is provided. Return product_id when possible. |
| order | order.validate_items, order.check_stock, order.calculate_total, order.review_order, confirm_order, help, cancel | confirmation (yes/no), delivery_method | order_notes | Ask for confirmation + delivery method together when possible. |
| payment | confirm_payment, payment.verify_status, help, cancel | payment_number | provider | Ask for mobile money number + account name in one message. |
| delivery | fulfillment.choose_method, fulfillment.choose_location, fulfillment.select_delivery_option, help, cancel | fulfillment_method, location | delivery_window | Ask delivery/pickup + location together in one message. |
| closed | help | none | none | Thank-you flow only; no new intents unless user reopens. |

## Stage Execution Policy (Multi-Stage in One Turn)

### Goal
Allow a single incoming message to advance through multiple stages sequentially, while respecting missing-slot checks and stage boundaries.

### Sequential Execution Rules
- Always start from the current session stage (or default to `chat`).
- Build a stage queue: `[current_stage, next_stage, next_stage...]`.
- Execute each stage in order until you hit a missing required slot or a safety limit.
- If a stage is completed, advance to the next stage in the same turn.
- If a required slot is missing, stop and ask for that slot (do not advance stages).

### Safety Limits
- Max stages per turn: 3
- Max handlers per stage: 5
- Max prompts per turn: 1 (ask multiple related slots in one message)

### Handler Sequence Examples
- chat: `greet_and_suggest` -> `product_suggestions` -> `cta`
- cart: `browse_catalogue` -> `select_product` -> `add_item` -> `view_cart`
- order: `order.validate_items` -> `order.check_stock` -> `order.review_order`
- payment: `confirm_payment` -> `payment.verify_status`
- delivery: `fulfillment.choose_method` -> `fulfillment.choose_location` -> `fulfillment.select_delivery_option`

### Multi-Slot Prompting
- Ask 2-3 related slots in one prompt (example: payment number + account name).
- For product selection, allow up to 5 items when a snapshot is provided.
- If ambiguous, ask a disambiguation question with top 3 matches.

## JSON Runtime Config (Single Source)

```json
{
  "version": "1.0",
  "product_matching": {
    "require_product_id": true,
    "max_suggestions_per_turn": 5,
    "snapshot_fields": ["id", "name", "price", "currency"]
  },
  "stages": {
    "chat": {
      "canonical_intents": [
        "greet_and_suggest",
        "help",
        "browse_catalogue",
        "view_cart",
        "add_item",
        "remove_item",
        "clear_cart",
        "cancel"
      ],
      "required_slots": [],
      "optional_slots": ["product_id", "product_name"],
      "multi_slot_question": {
        "max_items": 3,
        "notes": "If unclear, return greet_and_suggest; prefer product_id from snapshot."
      }
    },
    "cart": {
      "canonical_intents": [
        "browse_catalogue",
        "select_product",
        "inspect_item",
        "add_item",
        "remove_item",
        "view_cart",
        "clear_cart",
        "help",
        "cancel"
      ],
      "required_slots": ["product_id"],
      "optional_slots": ["product_name", "quantity", "category_id"],
      "multi_slot_question": {
        "max_items": 5,
        "notes": "Allow up to 5 product picks when snapshot exists; return product_id."
      }
    },
    "order": {
      "canonical_intents": [
        "order.validate_items",
        "order.check_stock",
        "order.calculate_total",
        "order.review_order",
        "confirm_order",
        "help",
        "cancel"
      ],
      "required_slots": ["confirmation", "delivery_method"],
      "optional_slots": ["order_notes"],
      "multi_slot_question": {
        "max_items": 2,
        "notes": "Ask confirmation + delivery method together when possible."
      }
    },
    "payment": {
      "canonical_intents": [
        "confirm_payment",
        "payment.verify_status",
        "help",
        "cancel"
      ],
      "required_slots": ["payment_number"],
      "optional_slots": ["provider"],
      "multi_slot_question": {
        "max_items": 2,
        "notes": "Ask mobile money number + account name in one message."
      }
    },
    "delivery": {
      "canonical_intents": [
        "fulfillment.choose_method",
        "fulfillment.choose_location",
        "fulfillment.select_delivery_option",
        "help",
        "cancel"
      ],
      "required_slots": ["fulfillment_method", "location"],
      "optional_slots": ["delivery_window"],
      "multi_slot_question": {
        "max_items": 2,
        "notes": "Ask delivery/pickup + location together in one message."
      }
    },
    "closed": {
      "canonical_intents": ["help"],
      "required_slots": [],
      "optional_slots": [],
      "multi_slot_question": {
        "max_items": 0,
        "notes": "Thank-you flow only; no new intents unless user reopens."
      }
    }
  }
}
```
