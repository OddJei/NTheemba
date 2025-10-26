"""User service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class UserServiceClient:
    """Client for user service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("USER_SERVICE")
        self.timeout = config.get_service_timeout("USER_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to user service"""
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
            logger.error(f"User service request failed: {e}")
            return {"error": f"User service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in user service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile"""
        try:
            result = self._make_request("GET", f"/users/{user_id}")
            
            if "error" not in result:
                logger.info(f"User profile retrieved: {user_id}")
            else:
                logger.warning(f"Failed to get user profile: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {"error": f"User profile error: {str(e)}"}
    
    def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        try:
            result = self._make_request("PUT", f"/users/{user_id}", profile_data)
            
            if "error" not in result:
                logger.info(f"User profile updated: {user_id}")
            else:
                logger.warning(f"Failed to update user profile: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return {"error": f"User profile update error: {str(e)}"}
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences"""
        try:
            result = self._make_request("GET", f"/users/{user_id}/preferences")
            
            if "error" not in result:
                logger.info(f"User preferences retrieved: {user_id}")
            else:
                logger.warning(f"Failed to get user preferences: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {"error": f"User preferences error: {str(e)}"}
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Update user preferences"""
        try:
            result = self._make_request("PUT", f"/users/{user_id}/preferences", preferences)
            
            if "error" not in result:
                logger.info(f"User preferences updated: {user_id}")
            else:
                logger.warning(f"Failed to update user preferences: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return {"error": f"User preferences update error: {str(e)}"}

