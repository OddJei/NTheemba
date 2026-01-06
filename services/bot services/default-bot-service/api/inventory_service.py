"""Inventory service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class InventoryServiceClient:
    """Client for inventory service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("INVENTORY_SERVICE")
        self.timeout = config.get_service_timeout("INVENTORY_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to inventory service"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                config.get("API_KEY_HEADER"): self.api_key
            }
            
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Inventory service request failed: {e}")
            return {"error": f"Inventory service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in inventory service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def check_stock(self, product_id: str, quantity: int = 1) -> Dict[str, Any]:
        """Check product stock availability"""
        try:
            data = {"product_id": product_id, "quantity": quantity}
            result = self._make_request("POST", "/inventory/check-stock", data)
            
            if "error" not in result:
                logger.info(f"Stock checked for product: {product_id}")
            else:
                logger.warning(f"Failed to check stock for product: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking stock: {e}")
            return {"error": f"Stock check error: {str(e)}"}
    
    def reserve_stock(self, product_id: str, quantity: int, order_id: str) -> Dict[str, Any]:
        """Reserve stock for order"""
        try:
            data = {
                "product_id": product_id,
                "quantity": quantity,
                "order_id": order_id
            }
            result = self._make_request("POST", "/inventory/reserve", data)
            
            if "error" not in result:
                logger.info(f"Stock reserved for product: {product_id}")
            else:
                logger.warning(f"Failed to reserve stock for product: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error reserving stock: {e}")
            return {"error": f"Stock reservation error: {str(e)}"}
    
    def release_stock(self, reservation_id: str) -> Dict[str, Any]:
        """Release reserved stock"""
        try:
            result = self._make_request("POST", f"/inventory/release/{reservation_id}")
            
            if "error" not in result:
                logger.info(f"Stock released: {reservation_id}")
            else:
                logger.warning(f"Failed to release stock: {reservation_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error releasing stock: {e}")
            return {"error": f"Stock release error: {str(e)}"}
    
    def get_inventory_levels(self, business_id: str = None) -> Dict[str, Any]:
        """Get inventory levels"""
        try:
            data = {}
            if business_id:
                data["business_id"] = business_id
            
            result = self._make_request("POST", "/inventory/levels", data)
            
            if "error" not in result:
                logger.info("Inventory levels retrieved")
            else:
                logger.warning("Failed to get inventory levels")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting inventory levels: {e}")
            return {"error": f"Inventory levels error: {str(e)}"}


