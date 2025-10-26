"""Event service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class EventServiceClient:
    """Client for event management service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("EVENT_SERVICE")
        self.timeout = config.get_service_timeout("EVENT_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to event service"""
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
            logger.error(f"Event service request failed: {e}")
            return {"error": f"Event service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in event service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def emit_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Emit single event"""
        try:
            result = self._make_request("POST", "/events", event)
            
            if "error" not in result:
                logger.info(f"Event emitted: {event.get('event_type', 'unknown')}")
            else:
                logger.warning(f"Failed to emit event: {event.get('event_type', 'unknown')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error emitting event: {e}")
            return {"error": f"Event emission error: {str(e)}"}
    
    def emit_events_batch(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Emit multiple events in batch"""
        try:
            data = {"events": events}
            result = self._make_request("POST", "/events/batch", data)
            
            if "error" not in result:
                logger.info(f"Batch events emitted: {len(events)} events")
            else:
                logger.warning(f"Failed to emit batch events: {len(events)} events")
            
            return result
            
        except Exception as e:
            logger.error(f"Error emitting batch events: {e}")
            return {"error": f"Batch event emission error: {str(e)}"}
    
    def get_event_history(self, session_id: str, limit: int = 100) -> Dict[str, Any]:
        """Get event history for session"""
        try:
            params = {"session_id": session_id, "limit": limit}
            result = self._make_request("GET", "/events/history", params)
            
            if "error" not in result:
                logger.info(f"Event history retrieved for session: {session_id}")
            else:
                logger.warning(f"Failed to get event history for session: {session_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting event history: {e}")
            return {"error": f"Event history error: {str(e)}"}
    
    def get_events_by_type(self, event_type: str, limit: int = 100) -> Dict[str, Any]:
        """Get events by type"""
        try:
            params = {"event_type": event_type, "limit": limit}
            result = self._make_request("GET", "/events/type", params)
            
            if "error" not in result:
                logger.info(f"Events retrieved by type: {event_type}")
            else:
                logger.warning(f"Failed to get events by type: {event_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting events by type: {e}")
            return {"error": f"Events by type error: {str(e)}"}
    
    def get_events_by_date_range(self, start_date: str, end_date: str, limit: int = 100) -> Dict[str, Any]:
        """Get events by date range"""
        try:
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit
            }
            result = self._make_request("GET", "/events/date-range", params)
            
            if "error" not in result:
                logger.info(f"Events retrieved by date range: {start_date} to {end_date}")
            else:
                logger.warning(f"Failed to get events by date range: {start_date} to {end_date}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting events by date range: {e}")
            return {"error": f"Events by date range error: {str(e)}"}
    
    def get_event_analytics(self, session_id: str = None, event_type: str = None) -> Dict[str, Any]:
        """Get event analytics"""
        try:
            params = {}
            if session_id:
                params["session_id"] = session_id
            if event_type:
                params["event_type"] = event_type
            
            result = self._make_request("GET", "/events/analytics", params)
            
            if "error" not in result:
                logger.info("Event analytics retrieved")
            else:
                logger.warning("Failed to get event analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting event analytics: {e}")
            return {"error": f"Event analytics error: {str(e)}"}
    
    def search_events(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Search events with query and filters"""
        try:
            data = {"query": query, "filters": filters or {}}
            result = self._make_request("POST", "/events/search", data)
            
            if "error" not in result:
                logger.info(f"Events searched with query: {query}")
            else:
                logger.warning(f"Failed to search events with query: {query}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching events: {e}")
            return {"error": f"Event search error: {str(e)}"}
    
    def export_events(self, filters: Dict[str, Any], format: str = "json") -> Dict[str, Any]:
        """Export events with filters"""
        try:
            data = {"filters": filters, "format": format}
            result = self._make_request("POST", "/events/export", data)
            
            if "error" not in result:
                logger.info("Events exported successfully")
            else:
                logger.warning("Failed to export events")
            
            return result
            
        except Exception as e:
            logger.error(f"Error exporting events: {e}")
            return {"error": f"Event export error: {str(e)}"}
    
    def get_event_metrics(self, time_range: str = "24h") -> Dict[str, Any]:
        """Get event metrics for time range"""
        try:
            params = {"time_range": time_range}
            result = self._make_request("GET", "/events/metrics", params)
            
            if "error" not in result:
                logger.info(f"Event metrics retrieved for: {time_range}")
            else:
                logger.warning(f"Failed to get event metrics for: {time_range}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting event metrics: {e}")
            return {"error": f"Event metrics error: {str(e)}"}