"""Payment service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class PaymentServiceClient:
    """Client for payment service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("PAYMENT_SERVICE")
        self.timeout = config.get_service_timeout("PAYMENT_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to payment service"""
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
            logger.error(f"Payment service request failed: {e}")
            return {"error": f"Payment service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in payment service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def initiate_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate payment"""
        try:
            result = self._make_request("POST", "/payments/initiate", payment_data)
            
            if "error" not in result:
                logger.info(f"Payment initiated: {result.get('payment_id', 'unknown')}")
            else:
                logger.warning("Failed to initiate payment")
            
            return result
            
        except Exception as e:
            logger.error(f"Error initiating payment: {e}")
            return {"error": f"Payment initiation error: {str(e)}"}
    
    def process_mobile_money_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process mobile money payment"""
        try:
            result = self._make_request("POST", "/payments/mobile-money", payment_data)
            
            if "error" not in result:
                logger.info("Mobile money payment processed")
            else:
                logger.warning("Failed to process mobile money payment")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing mobile money payment: {e}")
            return {"error": f"Mobile money payment error: {str(e)}"}
    
    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """Verify payment status"""
        try:
            result = self._make_request("GET", f"/payments/{payment_id}/verify")
            
            if "error" not in result:
                logger.info(f"Payment verified: {payment_id}")
            else:
                logger.warning(f"Failed to verify payment: {payment_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying payment: {e}")
            return {"error": f"Payment verification error: {str(e)}"}
    
    def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get payment status"""
        try:
            result = self._make_request("GET", f"/payments/{payment_id}/status")
            
            if "error" not in result:
                logger.info(f"Payment status retrieved: {payment_id}")
            else:
                logger.warning(f"Failed to get payment status: {payment_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting payment status: {e}")
            return {"error": f"Payment status error: {str(e)}"}
    
    def refund_payment(self, payment_id: str, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment refund"""
        try:
            result = self._make_request("POST", f"/payments/{payment_id}/refund", refund_data)
            
            if "error" not in result:
                logger.info(f"Payment refunded: {payment_id}")
            else:
                logger.warning(f"Failed to refund payment: {payment_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error refunding payment: {e}")
            return {"error": f"Payment refund error: {str(e)}"}
    
    def get_payment_methods(self) -> Dict[str, Any]:
        """Get available payment methods"""
        try:
            result = self._make_request("GET", "/payments/methods")
            
            if "error" not in result:
                logger.info("Payment methods retrieved")
            else:
                logger.warning("Failed to get payment methods")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting payment methods: {e}")
            return {"error": f"Payment methods error: {str(e)}"}
    
    def get_payment_history(self, user_id: str = None, limit: int = 50) -> Dict[str, Any]:
        """Get payment history"""
        try:
            data = {"limit": limit}
            if user_id:
                data["user_id"] = user_id
            
            result = self._make_request("POST", "/payments/history", data)
            
            if "error" not in result:
                logger.info(f"Payment history retrieved for user: {user_id}")
            else:
                logger.warning(f"Failed to get payment history for user: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting payment history: {e}")
            return {"error": f"Payment history error: {str(e)}"}
    
    def create_payment_link(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create payment link"""
        try:
            result = self._make_request("POST", "/payments/link", payment_data)
            
            if "error" not in result:
                logger.info("Payment link created")
            else:
                logger.warning("Failed to create payment link")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating payment link: {e}")
            return {"error": f"Payment link creation error: {str(e)}"}
    
    def get_payment_analytics(self, business_id: str = None, date_range: str = "30d") -> Dict[str, Any]:
        """Get payment analytics"""
        try:
            data = {"date_range": date_range}
            if business_id:
                data["business_id"] = business_id
            
            result = self._make_request("POST", "/payments/analytics", data)
            
            if "error" not in result:
                logger.info("Payment analytics retrieved")
            else:
                logger.warning("Failed to get payment analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting payment analytics: {e}")
            return {"error": f"Payment analytics error: {str(e)}"}


