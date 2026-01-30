"""Order service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class OrderServiceClient:
    """Client for order service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("ORDER_SERVICE")
        self.timeout = config.get_service_timeout("ORDER_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to order service"""
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
                params=params,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Order service request failed: {e}")
            return {"error": f"Order service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in order service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new order"""
        try:
            result = self._make_request("POST", "/orders", order_data)
            
            if "error" not in result:
                logger.info(f"Order created: {result.get('order_id', 'unknown')}")
            else:
                logger.warning("Failed to create order")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return {"error": f"Order creation error: {str(e)}"}
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order by ID"""
        try:
            result = self._make_request("GET", f"/orders/{order_id}")
            
            if "error" not in result:
                logger.info(f"Order retrieved: {order_id}")
            else:
                logger.warning(f"Failed to get order: {order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting order: {e}")
            return {"error": f"Order retrieval error: {str(e)}"}
    
    def update_order_status(self, order_id: str, status: str, notes: str = None) -> Dict[str, Any]:
        """Update order status"""
        try:
            data = {"status": status}
            if notes:
                data["notes"] = notes
            
            result = self._make_request("PUT", f"/orders/{order_id}/status", data)
            
            if "error" not in result:
                logger.info(f"Order status updated: {order_id} -> {status}")
            else:
                logger.warning(f"Failed to update order status: {order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating order status: {e}")
            return {"error": f"Order status update error: {str(e)}"}
    
    def get_user_orders(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get orders for user"""
        try:
            params = {
                "user_id": user_id,
                "limit": limit,
                "offset": offset
            }
            
            result = self._make_request("GET", "/orders/user", params=params)
            
            if "error" not in result:
                logger.info(f"User orders retrieved: {user_id}")
            else:
                logger.warning(f"Failed to get user orders: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return {"error": f"User orders error: {str(e)}"}
    
    def get_business_orders(self, business_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get orders for business (MSME)"""
        try:
            params = {
                "business_id": business_id,
                "limit": limit,
                "offset": offset
            }
            
            result = self._make_request("GET", "/orders/business", params=params)
            
            if "error" not in result:
                logger.info(f"Business orders retrieved: {business_id}")
            else:
                logger.warning(f"Failed to get business orders: {business_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting business orders: {e}")
            return {"error": f"Business orders error: {str(e)}"}
    
    def cancel_order(self, order_id: str, reason: str = None) -> Dict[str, Any]:
        """Cancel order"""
        try:
            data = {"reason": reason}
            result = self._make_request("POST", f"/orders/{order_id}/cancel", data)
            
            if "error" not in result:
                logger.info(f"Order cancelled: {order_id}")
            else:
                logger.warning(f"Failed to cancel order: {order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {"error": f"Order cancellation error: {str(e)}"}
    
    def add_order_item(self, order_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add item to order"""
        try:
            result = self._make_request("POST", f"/orders/{order_id}/items", item_data)
            
            if "error" not in result:
                logger.info(f"Item added to order: {order_id}")
            else:
                logger.warning(f"Failed to add item to order: {order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding order item: {e}")
            return {"error": f"Add order item error: {str(e)}"}
    
    def remove_order_item(self, order_id: str, item_id: str) -> Dict[str, Any]:
        """Remove item from order"""
        try:
            result = self._make_request("DELETE", f"/orders/{order_id}/items/{item_id}")
            
            if "error" not in result:
                logger.info(f"Item removed from order: {order_id}")
            else:
                logger.warning(f"Failed to remove item from order: {order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error removing order item: {e}")
            return {"error": f"Remove order item error: {str(e)}"}
    
    def calculate_order_total(self, order_id: str) -> Dict[str, Any]:
        """Calculate order total"""
        try:
            result = self._make_request("POST", f"/orders/{order_id}/calculate-total")
            
            if "error" not in result:
                logger.info(f"Order total calculated: {order_id}")
            else:
                logger.warning(f"Failed to calculate order total: {order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating order total: {e}")
            return {"error": f"Order total calculation error: {str(e)}"}
    
    def get_order_analytics(self, business_id: str = None, date_range: str = "30d") -> Dict[str, Any]:
        """Get order analytics"""
        try:
            params = {"date_range": date_range}
            if business_id:
                params["business_id"] = business_id
            
            result = self._make_request("GET", "/orders/analytics", params=params)
            
            if "error" not in result:
                logger.info("Order analytics retrieved")
            else:
                logger.warning("Failed to get order analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting order analytics: {e}")
            return {"error": f"Order analytics error: {str(e)}"}
    
    def search_orders(self, query: str, filters: Dict[str, Any] = None, limit: int = 50) -> Dict[str, Any]:
        """Search orders"""
        try:
            data = {
                "query": query,
                "filters": filters or {},
                "limit": limit
            }
            
            result = self._make_request("POST", "/orders/search", data)
            
            if "error" not in result:
                logger.info(f"Order search completed: {query}")
            else:
                logger.warning(f"Failed to search orders: {query}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching orders: {e}")
            return {"error": f"Order search error: {str(e)}"}
    
    def export_orders(self, filters: Dict[str, Any], format: str = "csv") -> Dict[str, Any]:
        """Export orders"""
        try:
            data = {"filters": filters, "format": format}
            result = self._make_request("POST", "/orders/export", data)
            
            if "error" not in result:
                logger.info("Orders exported successfully")
            else:
                logger.warning("Failed to export orders")
            
            return result
            
        except Exception as e:
            logger.error(f"Error exporting orders: {e}")
            return {"error": f"Order export error: {str(e)}"}



