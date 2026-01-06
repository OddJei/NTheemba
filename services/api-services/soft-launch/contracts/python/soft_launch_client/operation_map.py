from __future__ import annotations

from typing import Dict

from .models import OperationSpec


# Minimal default mapping. Adjust paths to match each service's router.
OPERATION_MAP: Dict[str, OperationSpec] = {
    "cart.create": OperationSpec(service="cart", method="POST", path="/cart/create"),
    "cart.add_item": OperationSpec(service="cart", method="POST", path="/cart/{cart_id}/add"),
    "cart.checkout": OperationSpec(service="cart", method="POST", path="/cart/{cart_id}/checkout"),
    "order.create": OperationSpec(service="order", method="POST", path="/order/create"),
    "order.set_status": OperationSpec(service="order", method="PUT", path="/order/{order_id}/status"),
    "payment.initiate": OperationSpec(service="payment-revenue", method="POST", path="/payment/initiate"),
    "payment.verify": OperationSpec(service="payment-revenue", method="POST", path="/payment/{payment_id}/verify"),
    "delivery.generate_code": OperationSpec(service="delivery", method="POST", path="/delivery/generate"),
    "delivery.confirm": OperationSpec(service="delivery", method="POST", path="/delivery/confirm"),
    "notify.send": OperationSpec(service="notification", method="POST", path="/notify/send"),

    # Catalog + Inventory (fused)
    "catalog.category_create": OperationSpec(service="catalog-inventory", method="POST", path="/catalog/category"),
    "catalog.category_get": OperationSpec(service="catalog-inventory", method="GET", path="/catalog/category/{id}"),
    "catalog.categories_list": OperationSpec(service="catalog-inventory", method="GET", path="/catalog/categories"),
    "catalog.product_create": OperationSpec(service="catalog-inventory", method="POST", path="/catalog/product"),
    "catalog.product_get": OperationSpec(service="catalog-inventory", method="GET", path="/catalog/product/{id}"),
    "catalog.variant_add": OperationSpec(service="catalog-inventory", method="POST", path="/catalog/product/{id}/variant"),
    "inventory.update": OperationSpec(service="catalog-inventory", method="POST", path="/inventory/update"),
    "inventory.get": OperationSpec(service="catalog-inventory", method="GET", path="/inventory/{variant_id}"),
}
