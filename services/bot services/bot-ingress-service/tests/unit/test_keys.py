from app.services import keys


def test_bot_keys():
    assert keys.bot_core("b1") == "bot:core:b1"
    assert keys.bot_by_phone("+260") == "bot:by_phone:+260"
    assert keys.bot_owner("o1") == "bot:owner:o1"
    assert keys.bot_config("b1") == "bot:config:b1"
    assert keys.bot_routing("b1") == "bot:routing:b1"
    assert keys.bot_policy("b1") == "bot:policy:b1"
    assert keys.bot_templates("b1", "en") == "bot:templates:b1:en"
    assert keys.bot_flow("b1", "v1") == "bot:flow:b1:v1"
    assert keys.bot_integrations("b1") == "bot:integrations:b1"
    assert keys.bot_kb("b1") == "bot:kb:b1"
    assert keys.bot_health("b1") == "bot:health:b1"


def test_catalog_keys():
    assert keys.catalog_index("biz1") == "bot:catalog:index:biz1"
    assert keys.catalog_product("p1") == "bot:catalog:product:p1"


def test_user_and_session_keys():
    assert keys.user_profile("u1") == "user:profile:u1"
    assert keys.user_by_phone("097", None) == "user:by_phone::097"
    assert keys.user_by_phone("097", "biz1") == "user:by_phone:biz1:097"
    assert keys.user_auth("u1", "biz1") == "user:auth:u1:biz1"
    assert keys.user_prefs("u1") == "user:prefs:u1"
    assert keys.user_addresses("u1") == "user:addresses:u1"
    assert keys.user_bot_relationship("u1", "b1") == "user:bot:u1:b1"

    assert keys.session_snapshot("s1") == "session:snapshot:s1"
    assert keys.session_context("s1") == "session:ctx:s1"
    assert keys.cart("c1") == "cart:c1"
    assert keys.order_draft("o1") == "order:draft:o1"
    assert keys.lock_hydrate("s1") == "lock:hydrate:s1"
    assert keys.neg_hydrate("s1") == "neg:hydrate:s1"
