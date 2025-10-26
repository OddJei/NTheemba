"""Analytics service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class AnalyticsServiceClient:
    """Client for analytics service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("ANALYTICS_SERVICE")
        self.timeout = config.get_service_timeout("ANALYTICS_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to analytics service"""
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
            logger.error(f"Analytics service request failed: {e}")
            return {"error": f"Analytics service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in analytics service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def get_sales_analytics(self, business_id: str = None, date_range: str = "30d") -> Dict[str, Any]:
        """Get sales analytics"""
        try:
            data = {"date_range": date_range}
            if business_id:
                data["business_id"] = business_id
            
            result = self._make_request("POST", "/analytics/sales", data)
            
            if "error" not in result:
                logger.info("Sales analytics retrieved")
            else:
                logger.warning("Failed to get sales analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting sales analytics: {e}")
            return {"error": f"Sales analytics error: {str(e)}"}
    
    def get_user_analytics(self, user_id: str = None, date_range: str = "30d") -> Dict[str, Any]:
        """Get user analytics"""
        try:
            data = {"date_range": date_range}
            if user_id:
                data["user_id"] = user_id
            
            result = self._make_request("POST", "/analytics/users", data)
            
            if "error" not in result:
                logger.info("User analytics retrieved")
            else:
                logger.warning("Failed to get user analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {"error": f"User analytics error: {str(e)}"}
    
    def get_product_analytics(self, product_id: str = None, date_range: str = "30d") -> Dict[str, Any]:
        """Get product analytics"""
        try:
            data = {"date_range": date_range}
            if product_id:
                data["product_id"] = product_id
            
            result = self._make_request("POST", "/analytics/products", data)
            
            if "error" not in result:
                logger.info("Product analytics retrieved")
            else:
                logger.warning("Failed to get product analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting product analytics: {e}")
            return {"error": f"Product analytics error: {str(e)}"}
    
    def get_custom_analytics(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get custom analytics"""
        try:
            data = {"query": query, "filters": filters or {}}
            result = self._make_request("POST", "/analytics/custom", data)
            
            if "error" not in result:
                logger.info("Custom analytics retrieved")
            else:
                logger.warning("Failed to get custom analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting custom analytics: {e}")
            return {"error": f"Custom analytics error: {str(e)}"}

