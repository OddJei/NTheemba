"""Auth service API client."""

import logging
import requests
from typing import Dict, Any, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class AuthServiceClient:
    """Client for authentication service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("AUTH_SERVICE")
        self.timeout = config.get_service_timeout("AUTH_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to auth service"""
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
            logger.error(f"Auth service request failed: {e}")
            return {"error": f"Auth service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in auth service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user with email and password"""
        try:
            data = {
                "email": email,
                "password": password
            }
            
            result = self._make_request("POST", "/auth/login", data)
            
            if "error" not in result:
                logger.info(f"User authenticated: {email}")
            else:
                logger.warning(f"Authentication failed for: {email}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return {"error": f"Authentication error: {str(e)}"}
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token"""
        try:
            data = {"token": token}
            result = self._make_request("POST", "/auth/validate", data)
            
            if "error" not in result:
                logger.info("Token validated successfully")
            else:
                logger.warning("Token validation failed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return {"error": f"Token validation error: {str(e)}"}
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information by ID"""
        try:
            result = self._make_request("GET", f"/auth/users/{user_id}")
            
            if "error" not in result:
                logger.info(f"User info retrieved: {user_id}")
            else:
                logger.warning(f"Failed to get user info: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {"error": f"User info error: {str(e)}"}
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh JWT token"""
        try:
            data = {"refresh_token": refresh_token}
            result = self._make_request("POST", "/auth/refresh", data)
            
            if "error" not in result:
                logger.info("Token refreshed successfully")
            else:
                logger.warning("Token refresh failed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return {"error": f"Token refresh error: {str(e)}"}
    
    def logout_user(self, user_id: str, token: str) -> Dict[str, Any]:
        """Logout user"""
        try:
            data = {
                "user_id": user_id,
                "token": token
            }
            result = self._make_request("POST", "/auth/logout", data)
            
            if "error" not in result:
                logger.info(f"User logged out: {user_id}")
            else:
                logger.warning(f"Logout failed for: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            return {"error": f"Logout error: {str(e)}"}
    
    def get_user_roles(self, user_id: str) -> Dict[str, Any]:
        """Get user roles and permissions"""
        try:
            result = self._make_request("GET", f"/auth/users/{user_id}/roles")
            
            if "error" not in result:
                logger.info(f"User roles retrieved: {user_id}")
            else:
                logger.warning(f"Failed to get user roles: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user roles: {e}")
            return {"error": f"User roles error: {str(e)}"}
    
    def check_permission(self, user_id: str, permission: str) -> Dict[str, Any]:
        """Check if user has specific permission"""
        try:
            data = {
                "user_id": user_id,
                "permission": permission
            }
            result = self._make_request("POST", "/auth/permissions/check", data)
            
            if "error" not in result:
                logger.info(f"Permission checked: {permission} for {user_id}")
            else:
                logger.warning(f"Permission check failed: {permission} for {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return {"error": f"Permission check error: {str(e)}"}