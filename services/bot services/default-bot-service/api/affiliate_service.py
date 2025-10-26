"""Affiliate service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class AffiliateServiceClient:
    """Client for affiliate service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("AFFILIATE_SERVICE")
        self.timeout = config.get_service_timeout("AFFILIATE_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to affiliate service"""
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
            logger.error(f"Affiliate service request failed: {e}")
            return {"error": f"Affiliate service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in affiliate service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def get_affiliate_profile(self, affiliate_id: str) -> Dict[str, Any]:
        """Get affiliate profile"""
        try:
            result = self._make_request("GET", f"/affiliates/{affiliate_id}")
            
            if "error" not in result:
                logger.info(f"Affiliate profile retrieved: {affiliate_id}")
            else:
                logger.warning(f"Failed to get affiliate profile: {affiliate_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting affiliate profile: {e}")
            return {"error": f"Affiliate profile error: {str(e)}"}
    
    def get_commission_summary(self, affiliate_id: str) -> Dict[str, Any]:
        """Get commission summary"""
        try:
            result = self._make_request("GET", f"/affiliates/{affiliate_id}/commissions")
            
            if "error" not in result:
                logger.info(f"Commission summary retrieved: {affiliate_id}")
            else:
                logger.warning(f"Failed to get commission summary: {affiliate_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting commission summary: {e}")
            return {"error": f"Commission summary error: {str(e)}"}
    
    def create_referral_link(self, affiliate_id: str, product_id: str) -> Dict[str, Any]:
        """Create referral link"""
        try:
            data = {
                "affiliate_id": affiliate_id,
                "product_id": product_id
            }
            result = self._make_request("POST", "/affiliates/referral-links", data)
            
            if "error" not in result:
                logger.info(f"Referral link created: {affiliate_id}")
            else:
                logger.warning(f"Failed to create referral link: {affiliate_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating referral link: {e}")
            return {"error": f"Referral link creation error: {str(e)}"}
    
    def get_referral_analytics(self, affiliate_id: str) -> Dict[str, Any]:
        """Get referral analytics"""
        try:
            result = self._make_request("GET", f"/affiliates/{affiliate_id}/analytics")
            
            if "error" not in result:
                logger.info(f"Referral analytics retrieved: {affiliate_id}")
            else:
                logger.warning(f"Failed to get referral analytics: {affiliate_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting referral analytics: {e}")
            return {"error": f"Referral analytics error: {str(e)}"}

