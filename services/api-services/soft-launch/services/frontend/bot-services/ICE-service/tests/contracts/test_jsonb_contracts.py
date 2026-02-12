"""Phase 7: JSONB Contract Validation Tests

Validates that ICE service JSONB blobs conform to bot service contracts.
"""

import pytest
import json
from datetime import datetime, timedelta
from jsonschema import validate, ValidationError


# Contract Schemas (from contracts/python/soft_launch_client/)

SCHEMAS = {
    "session": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "user_id": {"type": "string"},
            "user_phone": {"type": "string"},
            "bot_id": {"type": "string"},
            "platform": {"type": "string", "enum": ["WHATSAPP", "MESSENGER", "TELEGRAM", "TELEGRAM_BOT"]},
            "bot_type": {"type": "string", "enum": ["MSME", "CART", "DELIVERY", "PAYMENT"]},
            "session_start": {"type": "string", "format": "date-time"},
            "last_activity": {"type": "string", "format": "date-time"},
            "session_state": {
                "type": "object",
                "properties": {
                    "current_node": {"type": "string"},
                    "breadcrumbs": {"type": "array", "items": {"type": "string"}},
                    "context_vars": {"type": "object"}
                }
            },
            "interaction_count": {"type": "integer", "minimum": 0},
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "event_type": {"type": "string"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "data": {"type": "object"}
                    },
                    "required": ["event_id", "event_type", "timestamp"]
                }
            }
        },
        "required": ["session_id", "user_id", "user_phone", "bot_id", "platform", "bot_type"],
        "additionalProperties": True
    },
    
    "order_draft": {
        "type": "object",
        "properties": {
            "order_draft_id": {"type": "string"},
            "session_id": {"type": "string"},
            "business_id": {"type": "string"},
            "cart_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "sku": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1},
                        "unit_price_minor": {"type": "integer", "minimum": 0},
                        "total_price_minor": {"type": "integer", "minimum": 0},
                        "name": {"type": "string"},
                        "variant": {"type": "string"}
                    },
                    "required": ["product_id", "sku", "quantity", "unit_price_minor", "total_price_minor"]
                }
            },
            "cart_total_minor": {"type": "integer", "minimum": 0},
            "cart_currency": {"type": "string", "minLength": 3, "maxLength": 3},
            "payment_method": {"type": "string", "enum": ["MOBILE_MONEY", "CARD", "COD", "BANK_TRANSFER"]},
            "delivery_method": {"type": "string", "enum": ["DELIVERY", "PICKUP", "COURIER"]},
            "status": {"type": "string", "enum": ["DRAFT", "RESERVED", "CONFIRMED", "CANCELLED"]},
            "created_at": {"type": "string", "format": "date-time"},
            "reserved_until": {"type": ["string", "null"], "format": "date-time"},
            "reserved_ref": {"type": ["string", "null"]}
        },
        "required": ["order_draft_id", "session_id", "business_id", "cart_items", "cart_total_minor", "cart_currency", "status"],
        "additionalProperties": True
    },
    
    "bot_meta": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "bot_instance_id": {"type": "string"},
            "engine_version": {"type": "string"},
            "last_intent": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "entities": {"type": "object"},
                    "timestamp": {"type": "string", "format": "date-time"}
                }
            },
            "slots": {"type": "object"},
            "session_flags": {
                "type": "object",
                "properties": {
                    "is_returning_user": {"type": "boolean"},
                    "has_active_order": {"type": "boolean"},
                    "language": {"type": "string"}
                }
            }
        },
        "required": ["session_id", "bot_instance_id"],
        "additionalProperties": True
    }
}


class TestJSONBContracts:
    """Validate JSONB shapes match bot expectations."""
    
    def test_session_blob_valid(self):
        """Session blob adheres to contract."""
        
        session_data = {
            "session_id": "sess_001",
            "user_id": "user_001",
            "user_phone": "+260970000001",
            "bot_id": "msme_bot_v1",
            "platform": "WHATSAPP",
            "bot_type": "MSME",
            "session_start": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "session_state": {
                "current_node": "main_menu",
                "breadcrumbs": ["welcome", "main_menu"],
                "context_vars": {"selected_product": "solar_panel"}
            },
            "interaction_count": 3,
            "events": [
                {
                    "event_id": "evt_001",
                    "event_type": "user_message",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {"text": "hello"}
                }
            ]
        }
        
        # Should not raise ValidationError
        validate(instance=session_data, schema=SCHEMAS["session"])
    
    def test_session_blob_missing_required(self):
        """Session blob fails if required fields missing."""
        
        invalid_session = {
            "session_id": "sess_001",
            "user_id": "user_001"
            # Missing: user_phone, bot_id, platform, bot_type
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_session, schema=SCHEMAS["session"])
    
    def test_session_blob_invalid_platform(self):
        """Session blob fails on invalid platform enum."""
        
        invalid_session = {
            "session_id": "sess_001",
            "user_id": "user_001",
            "user_phone": "+260970000001",
            "bot_id": "bot_001",
            "platform": "INVALID_PLATFORM",  # Should be WHATSAPP|MESSENGER|TELEGRAM|TELEGRAM_BOT
            "bot_type": "MSME"
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_session, schema=SCHEMAS["session"])
    
    def test_order_draft_blob_valid(self):
        """Order draft blob adheres to contract."""
        
        order_data = {
            "order_draft_id": "ord_001",
            "session_id": "sess_001",
            "business_id": "biz_001",
            "cart_items": [
                {
                    "product_id": "prod_001",
                    "sku": "SOLAR-PANEL-100W",
                    "quantity": 2,
                    "unit_price_minor": 50000,
                    "total_price_minor": 100000,
                    "name": "Solar Panel 100W",
                    "variant": "blue"
                }
            ],
            "cart_total_minor": 100000,
            "cart_currency": "ZMW",
            "payment_method": "MOBILE_MONEY",
            "delivery_method": "DELIVERY",
            "status": "DRAFT",
            "created_at": datetime.utcnow().isoformat()
        }
        
        validate(instance=order_data, schema=SCHEMAS["order_draft"])
    
    def test_order_draft_invalid_status(self):
        """Order draft fails on invalid status."""
        
        invalid_order = {
            "order_draft_id": "ord_001",
            "session_id": "sess_001",
            "business_id": "biz_001",
            "cart_items": [],
            "cart_total_minor": 0,
            "cart_currency": "ZMW",
            "status": "INVALID_STATUS"  # Should be DRAFT|RESERVED|CONFIRMED|CANCELLED
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_order, schema=SCHEMAS["order_draft"])
    
    def test_order_draft_invalid_currency(self):
        """Order draft currency must be 3-char ISO code."""
        
        invalid_order = {
            "order_draft_id": "ord_001",
            "session_id": "sess_001",
            "business_id": "biz_001",
            "cart_items": [],
            "cart_total_minor": 0,
            "cart_currency": "Z",  # Should be 3 chars
            "status": "DRAFT"
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_order, schema=SCHEMAS["order_draft"])
    
    def test_order_draft_invalid_payment_method(self):
        """Order draft fails on invalid payment method."""
        
        invalid_order = {
            "order_draft_id": "ord_001",
            "session_id": "sess_001",
            "business_id": "biz_001",
            "cart_items": [],
            "cart_total_minor": 0,
            "cart_currency": "ZMW",
            "payment_method": "BITCOIN",  # Invalid
            "status": "DRAFT"
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_order, schema=SCHEMAS["order_draft"])
    
    def test_bot_meta_blob_valid(self):
        """Bot meta blob adheres to contract."""
        
        bot_meta = {
            "session_id": "sess_001",
            "bot_instance_id": "bot_inst_001",
            "engine_version": "1.2.3",
            "last_intent": {
                "intent": "checkout",
                "confidence": 0.95,
                "entities": {"product_id": "prod_001"},
                "timestamp": datetime.utcnow().isoformat()
            },
            "slots": {"product_id": "prod_001", "quantity": 2},
            "session_flags": {
                "is_returning_user": True,
                "has_active_order": False,
                "language": "en"
            }
        }
        
        validate(instance=bot_meta, schema=SCHEMAS["bot_meta"])
    
    def test_bot_meta_invalid_confidence(self):
        """Bot meta confidence must be 0-1."""
        
        invalid_meta = {
            "session_id": "sess_001",
            "bot_instance_id": "bot_inst_001",
            "last_intent": {
                "intent": "checkout",
                "confidence": 1.5  # Should be 0-1
            }
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_meta, schema=SCHEMAS["bot_meta"])
    
    def test_multiple_blobs_in_response(self):
        """Validate multiple blobs together (hydration response)."""
        
        hydration_response = {
            "session_blob": {
                "session_id": "sess_001",
                "user_id": "user_001",
                "user_phone": "+260970000001",
                "bot_id": "bot_001",
                "platform": "WHATSAPP",
                "bot_type": "MSME",
                "session_start": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat()
            },
            "order_draft_blob": {
                "order_draft_id": "ord_001",
                "session_id": "sess_001",
                "business_id": "biz_001",
                "cart_items": [],
                "cart_total_minor": 0,
                "cart_currency": "ZMW",
                "status": "DRAFT",
                "created_at": datetime.utcnow().isoformat()
            },
            "bot_meta_blob": {
                "session_id": "sess_001",
                "bot_instance_id": "bot_inst_001"
            }
        }
        
        # Validate each blob independently
        validate(instance=hydration_response["session_blob"], schema=SCHEMAS["session"])
        validate(instance=hydration_response["order_draft_blob"], schema=SCHEMAS["order_draft"])
        validate(instance=hydration_response["bot_meta_blob"], schema=SCHEMAS["bot_meta"])


class TestContractEvolution:
    """Test backward compatibility during schema migrations."""
    
    def test_new_optional_field_backward_compatible(self):
        """Adding optional field doesn't break old clients."""
        
        old_session = {
            "session_id": "sess_001",
            "user_id": "user_001",
            "user_phone": "+260970000001",
            "bot_id": "bot_001",
            "platform": "WHATSAPP",
            "bot_type": "MSME"
            # Missing: optional fields
        }
        
        # Should pass: new fields are optional
        validate(instance=old_session, schema=SCHEMAS["session"])
    
    def test_additional_properties_allowed(self):
        """Extra fields in blob don't cause validation failure."""
        
        session_with_extra = {
            "session_id": "sess_001",
            "user_id": "user_001",
            "user_phone": "+260970000001",
            "bot_id": "bot_001",
            "platform": "WHATSAPP",
            "bot_type": "MSME",
            "custom_field_1": "value_1",
            "custom_field_2": {"nested": "value"}
        }
        
        # Should pass: additionalProperties: true
        validate(instance=session_with_extra, schema=SCHEMAS["session"])
    
    def test_enum_stability(self):
        """Enum values remain stable across versions."""
        
        valid_platforms = ["WHATSAPP", "MESSENGER", "TELEGRAM", "TELEGRAM_BOT"]
        valid_bot_types = ["MSME", "CART", "DELIVERY", "PAYMENT"]
        valid_statuses = ["DRAFT", "RESERVED", "CONFIRMED", "CANCELLED"]
        
        for platform in valid_platforms:
            session = {
                "session_id": "sess_001",
                "user_id": "user_001",
                "user_phone": "+260970000001",
                "bot_id": "bot_001",
                "platform": platform,
                "bot_type": "MSME"
            }
            validate(instance=session, schema=SCHEMAS["session"])
        
        for bot_type in valid_bot_types:
            session = {
                "session_id": "sess_001",
                "user_id": "user_001",
                "user_phone": "+260970000001",
                "bot_id": "bot_001",
                "platform": "WHATSAPP",
                "bot_type": bot_type
            }
            validate(instance=session, schema=SCHEMAS["session"])
        
        for status in valid_statuses:
            order = {
                "order_draft_id": "ord_001",
                "session_id": "sess_001",
                "business_id": "biz_001",
                "cart_items": [],
                "cart_total_minor": 0,
                "cart_currency": "ZMW",
                "status": status
            }
            validate(instance=order, schema=SCHEMAS["order_draft"])


class TestFieldValidation:
    """Test field-level validation rules."""
    
    def test_cart_item_quantity_minimum(self):
        """Cart item quantity must be >= 1."""
        
        invalid_order = {
            "order_draft_id": "ord_001",
            "session_id": "sess_001",
            "business_id": "biz_001",
            "cart_items": [
                {
                    "product_id": "prod_001",
                    "sku": "SKU-001",
                    "quantity": 0,  # Invalid: must be >= 1
                    "unit_price_minor": 50000,
                    "total_price_minor": 0
                }
            ],
            "cart_total_minor": 0,
            "cart_currency": "ZMW",
            "status": "DRAFT"
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_order, schema=SCHEMAS["order_draft"])
    
    def test_price_non_negative(self):
        """Prices must be non-negative."""
        
        invalid_order = {
            "order_draft_id": "ord_001",
            "session_id": "sess_001",
            "business_id": "biz_001",
            "cart_items": [
                {
                    "product_id": "prod_001",
                    "sku": "SKU-001",
                    "quantity": 1,
                    "unit_price_minor": -100,  # Invalid
                    "total_price_minor": -100
                }
            ],
            "cart_total_minor": 0,
            "cart_currency": "ZMW",
            "status": "DRAFT"
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_order, schema=SCHEMAS["order_draft"])
    
    def test_interaction_count_non_negative(self):
        """Interaction count must be >= 0."""
        
        invalid_session = {
            "session_id": "sess_001",
            "user_id": "user_001",
            "user_phone": "+260970000001",
            "bot_id": "bot_001",
            "platform": "WHATSAPP",
            "bot_type": "MSME",
            "interaction_count": -1  # Invalid
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_session, schema=SCHEMAS["session"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
