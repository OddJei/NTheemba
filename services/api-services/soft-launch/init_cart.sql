CREATE SCHEMA IF NOT EXISTS cart;

CREATE TABLE cart.carts (
    id VARCHAR NOT NULL PRIMARY KEY,
    session_id VARCHAR,
    user_phone VARCHAR,
    user_id VARCHAR,
    business_id VARCHAR,
    status VARCHAR DEFAULT 'active' NOT NULL,
    metadata JSON,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE cart.cart_items (
    id VARCHAR NOT NULL PRIMARY KEY,
    cart_id VARCHAR NOT NULL,
    variant_id VARCHAR NOT NULL,
    product_name VARCHAR,
    media_url VARCHAR,
    quantity INTEGER DEFAULT 1 NOT NULL,
    reserved_quantity INTEGER DEFAULT 0 NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE cart.idempotency_records (
    id VARCHAR NOT NULL PRIMARY KEY,
    scope VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    status_code INTEGER NOT NULL,
    response_json JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_idempotency_scope_key UNIQUE (scope, key)
);

CREATE TABLE cart.outbox_events (
    id VARCHAR NOT NULL PRIMARY KEY,
    event_type VARCHAR NOT NULL,
    business_id VARCHAR,
    entity_type VARCHAR,
    entity_id VARCHAR,
    payload JSON NOT NULL,
    processed BOOLEAN DEFAULT FALSE NOT NULL,
    correlation_id VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_carts_session_id ON cart.carts(session_id);
CREATE INDEX idx_carts_user_phone ON cart.carts(user_phone);
CREATE INDEX idx_carts_user_id ON cart.carts(user_id);
CREATE INDEX idx_carts_business_id ON cart.carts(business_id);
CREATE INDEX idx_cart_items_cart_id ON cart.cart_items(cart_id);
CREATE INDEX idx_cart_items_variant_id ON cart.cart_items(variant_id);
CREATE INDEX idx_outbox_business_id ON cart.outbox_events(business_id);
