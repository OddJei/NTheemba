"""Business service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class BusinessServiceClient:
    """Client for business service (MSME)"""
    
    def __init__(self):
        self.base_url = config.get_service_url("BUSINESS_SERVICE")
        self.timeout = config.get_service_timeout("BUSINESS_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to business service"""
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
            logger.error(f"Business service request failed: {e}")
            return {"error": f"Business service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in business service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def get_business_profile(self, business_id: str) -> Dict[str, Any]:
        """Get business profile"""
        try:
            result = self._make_request("GET", f"/businesses/{business_id}")
            
            if "error" not in result:
                logger.info(f"Business profile retrieved: {business_id}")
            else:
                logger.warning(f"Failed to get business profile: {business_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting business profile: {e}")
            return {"error": f"Business profile error: {str(e)}"}
    
    def update_business_profile(self, business_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update business profile"""
        try:
            result = self._make_request("PUT", f"/businesses/{business_id}", profile_data)
            
            if "error" not in result:
                logger.info(f"Business profile updated: {business_id}")
            else:
                logger.warning(f"Failed to update business profile: {business_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating business profile: {e}")
            return {"error": f"Business profile update error: {str(e)}"}
    
    def get_business_products(self, business_id: str) -> Dict[str, Any]:
        """Get business products"""
        try:
            result = self._make_request("GET", f"/businesses/{business_id}/products")
            
            if "error" not in result:
                logger.info(f"Business products retrieved: {business_id}")
            else:
                logger.warning(f"Failed to get business products: {business_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting business products: {e}")
            return {"error": f"Business products error: {str(e)}"}
    
    def get_business_analytics(self, business_id: str) -> Dict[str, Any]:
        """Get business analytics"""
        try:
            result = self._make_request("GET", f"/businesses/{business_id}/analytics")
            
            if "error" not in result:
                logger.info(f"Business analytics retrieved: {business_id}")
            else:
                logger.warning(f"Failed to get business analytics: {business_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting business analytics: {e}")
            return {"error": f"Business analytics error: {str(e)}"}



