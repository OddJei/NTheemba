import sys
import time
import httpx

MSME = "http://localhost:8500"
ORDER = "http://localhost:8560"

print('Starting E2E demo: msme -> order-delivery')

# 1. Register business
import uuid

suffix = uuid.uuid4().hex[:6]
biz_payload = {
    "name": f"Test Biz E2E {suffix}",
    "location": "Lusaka",
    "category": "retail",
    "owner": {
        "username": f"e2e_owner_{suffix}",
        "email": f"e2e_owner_{suffix}@example.com",
        "phone": f"0777{suffix[:6]}",
        "password": "password123"
    },
    "delivery_locations": {},
}

with httpx.Client(timeout=10.0) as c:
    r = c.post(f"{MSME}/business/register", json=biz_payload)
    print('business.register', r.status_code, r.text)
    if r.status_code not in (200,201):
        print('Failed to register business')
        sys.exit(1)
    body = r.json()
    business = body.get('business') or body
    business_id = business.get('id')
    print('business_id=', business_id)

    # 2. Request service token for business
    r = c.post(f"{MSME}/auth/service-token/{business_id}")
    print('service-token', r.status_code, r.text)
    if r.status_code not in (200,201):
        print('Failed to get service token')
        sys.exit(1)
    tokens = r.json()
    access = tokens.get('access_token') or tokens.get('accessToken') or tokens.get('accessToken')
    if not access:
        access = tokens.get('access_token') or tokens.get('accessToken')
    headers = {'Authorization': f'Bearer {access}'}

    # 3. Set delivery locations
    dl_payload = {
        "delivery_locations": {
            "Lusaka": {"price_minor": 2500, "currency": "ZMW"},
            "Kitwe": {"price_minor": 1800, "currency": "ZMW"}
        }
    }
    # endpoint expects a payload with key `delivery_locations`
    r = c.put(f"{MSME}/businesses/{business_id}/delivery-locations", json=dl_payload, headers=headers)
    print('set delivery-locations', r.status_code, r.text)

    # 4. Create an order with deliver_to_customer choosing Lusaka
    order_payload = {
        "user_phone": "0777000002",
        "business_id": business_id,
        "delivery_method": "deliver_to_customer",
        "total_amount": 1000,
        "currency": "ZMW",
        "metadata": {"delivery_location": "Lusaka", "items": [{"product_id": "sku-1", "qty": 1}]}
    }
    r = c.post(f"{ORDER}/orders/create", json=order_payload, headers=headers)
    print('create order', r.status_code, r.text)
    if r.status_code not in (200,201):
        print('Order create failed')
        sys.exit(1)
    order = r.json()
    order_id = order.get('id')
    print('order id', order_id)

    # 5. Update delivery location to Kitwe
    upd = {"delivery_location": "Kitwe"}
    r = c.put(f"{ORDER}/orders/{order_id}/delivery_location", json=upd, headers=headers)
    print('update delivery_location', r.status_code, r.text)
    if r.status_code not in (200,201):
        print('Update failed')
        sys.exit(1)
    print('Done')
