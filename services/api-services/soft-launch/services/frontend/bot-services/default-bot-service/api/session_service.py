"""Session service API client."""

import logging
import requests
from typing import Dict, Any, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class SessionServiceClient:
    """Client for session management service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("SESSION_SERVICE")
        self.timeout = config.get_service_timeout("SESSION_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to session service"""
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
            logger.error(f"Session service request failed: {e}")
            return {"error": f"Session service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in session service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def create_session(self, user_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new session"""
        try:
            data = {
                "user_id": user_id,
                "session_data": session_data
            }
            
            result = self._make_request("POST", "/sessions", data)
            
            if "error" not in result:
                logger.info(f"Session created for user: {user_id}")
            else:
                logger.warning(f"Failed to create session for user: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return {"error": f"Session creation error: {str(e)}"}
    
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session by ID"""
        try:
            result = self._make_request("GET", f"/sessions/{session_id}")
            
            if "error" not in result:
                logger.info(f"Session retrieved: {session_id}")
            else:
                logger.warning(f"Failed to get session: {session_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return {"error": f"Session retrieval error: {str(e)}"}
    
    def update_session(self, session_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing session"""
        try:
            data = {"session_data": session_data}
            result = self._make_request("PUT", f"/sessions/{session_id}", data)
            
            if "error" not in result:
                logger.info(f"Session updated: {session_id}")
            else:
                logger.warning(f"Failed to update session: {session_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return {"error": f"Session update error: {str(e)}"}
    
    def delete_session(self, session_id: str) -> Dict[str, Any]:
        """Delete session"""
        try:
            result = self._make_request("DELETE", f"/sessions/{session_id}")
            
            if "error" not in result:
                logger.info(f"Session deleted: {session_id}")
            else:
                logger.warning(f"Failed to delete session: {session_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return {"error": f"Session deletion error: {str(e)}"}
    
    def extend_session(self, session_id: str, ttl_seconds: int) -> Dict[str, Any]:
        """Extend session TTL"""
        try:
            data = {"ttl_seconds": ttl_seconds}
            result = self._make_request("POST", f"/sessions/{session_id}/extend", data)
            
            if "error" not in result:
                logger.info(f"Session extended: {session_id}")
            else:
                logger.warning(f"Failed to extend session: {session_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extending session: {e}")
            return {"error": f"Session extension error: {str(e)}"}
    
    def get_user_sessions(self, user_id: str) -> Dict[str, Any]:
        """Get all sessions for user"""
        try:
            result = self._make_request("GET", f"/sessions/user/{user_id}")
            
            if "error" not in result:
                logger.info(f"User sessions retrieved: {user_id}")
            else:
                logger.warning(f"Failed to get user sessions: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return {"error": f"User sessions error: {str(e)}"}
    
    def cleanup_expired_sessions(self) -> Dict[str, Any]:
        """Cleanup expired sessions"""
        try:
            result = self._make_request("POST", "/sessions/cleanup")
            
            if "error" not in result:
                logger.info("Expired sessions cleaned up")
            else:
                logger.warning("Failed to cleanup expired sessions")
            
            return result
            
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return {"error": f"Session cleanup error: {str(e)}"}
    
    def get_session_analytics(self, session_id: str) -> Dict[str, Any]:
        """Get session analytics"""
        try:
            result = self._make_request("GET", f"/sessions/{session_id}/analytics")
            
            if "error" not in result:
                logger.info(f"Session analytics retrieved: {session_id}")
            else:
                logger.warning(f"Failed to get session analytics: {session_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting session analytics: {e}")
            return {"error": f"Session analytics error: {str(e)}"}