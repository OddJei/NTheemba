"""Event emitter for bot service events."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json

logger = logging.getLogger(__name__)

class EventEmitter:
    """Handles emission of structured events to the User-Bot Event Service"""
    
    def __init__(self, redis_client=None, event_service_client=None):
        self.redis_client = redis_client
        self.event_service_client = event_service_client
    
    def emit_node_activated(self, 
                          session_id: str, 
                          node_name: str, 
                          intent: str, 
                          metadata: Dict[str, Any] = None) -> bool:
        """Emit node activated event"""
        try:
            event = {
                "event_type": "node_activated",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "node_name": node_name,
                "intent": intent,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Node activated event emitted: {node_name} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting node activated event: {e}")
            return False
    
    def emit_action_performed(self, 
                            session_id: str, 
                            action: str, 
                            result: Dict[str, Any], 
                            metadata: Dict[str, Any] = None) -> bool:
        """Emit action performed event"""
        try:
            event = {
                "event_type": "action_performed",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "action": action,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Action performed event emitted: {action} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting action performed event: {e}")
            return False
    
    def emit_tree_switched(self, 
                         session_id: str, 
                         from_tree: str, 
                         to_tree: str, 
                         reason: str, 
                         metadata: Dict[str, Any] = None) -> bool:
        """Emit tree switched event"""
        try:
            event = {
                "event_type": "tree_switched",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "from_tree": from_tree,
                "to_tree": to_tree,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Tree switched event emitted: {from_tree} -> {to_tree} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting tree switched event: {e}")
            return False
    
    def emit_session_created(self, 
                           session_id: str, 
                           user_id: str, 
                           session_mode: str, 
                           metadata: Dict[str, Any] = None) -> bool:
        """Emit session created event"""
        try:
            event = {
                "event_type": "session_created",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "session_mode": session_mode,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Session created event emitted: {session_id} for user {user_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting session created event: {e}")
            return False
    
    def emit_session_updated(self, 
                           session_id: str, 
                           update_type: str, 
                           changes: Dict[str, Any], 
                           metadata: Dict[str, Any] = None) -> bool:
        """Emit session updated event"""
        try:
            event = {
                "event_type": "session_updated",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "update_type": update_type,
                "changes": changes,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Session updated event emitted: {update_type} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting session updated event: {e}")
            return False
    
    def emit_error_occurred(self, 
                           session_id: str, 
                           error_type: str, 
                           error_message: str, 
                           node_name: str = None, 
                           metadata: Dict[str, Any] = None) -> bool:
        """Emit error occurred event"""
        try:
            event = {
                "event_type": "error_occurred",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "error_type": error_type,
                "error_message": error_message,
                "node_name": node_name,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Error occurred event emitted: {error_type} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting error occurred event: {e}")
            return False
    
    def emit_handler_executed(self, 
                            session_id: str, 
                            handler_name: str, 
                            execution_result: Dict[str, Any], 
                            execution_time: float, 
                            metadata: Dict[str, Any] = None) -> bool:
        """Emit handler executed event"""
        try:
            event = {
                "event_type": "handler_executed",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "handler_name": handler_name,
                "execution_result": execution_result,
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Handler executed event emitted: {handler_name} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting handler executed event: {e}")
            return False
    
    def emit_user_interaction(self, 
                            session_id: str, 
                            interaction_type: str, 
                            user_input: str, 
                            bot_response: str, 
                            metadata: Dict[str, Any] = None) -> bool:
        """Emit user interaction event"""
        try:
            event = {
                "event_type": "user_interaction",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "interaction_type": interaction_type,
                "user_input": user_input,
                "bot_response": bot_response,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"User interaction event emitted: {interaction_type} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting user interaction event: {e}")
            return False
    
    def emit_business_event(self, 
                           session_id: str, 
                           business_id: str, 
                           event_type: str, 
                           business_data: Dict[str, Any], 
                           metadata: Dict[str, Any] = None) -> bool:
        """Emit business-specific event (for MSME operations)"""
        try:
            event = {
                "event_type": f"business_{event_type}",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "business_id": business_id,
                "business_event_type": event_type,
                "business_data": business_data,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Business event emitted: {event_type} for business {business_id} in session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting business event: {e}")
            return False
    
    def emit_affiliate_event(self, 
                            session_id: str, 
                            affiliate_id: str, 
                            event_type: str, 
                            affiliate_data: Dict[str, Any], 
                            metadata: Dict[str, Any] = None) -> bool:
        """Emit affiliate-specific event"""
        try:
            event = {
                "event_type": f"affiliate_{event_type}",
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "affiliate_id": affiliate_id,
                "affiliate_event_type": event_type,
                "affiliate_data": affiliate_data,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Affiliate event emitted: {event_type} for affiliate {affiliate_id} in session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting affiliate event: {e}")
            return False
    
    def _emit_event(self, event: Dict[str, Any]) -> bool:
        """Internal method to emit event to event service"""
        try:
            # Try to emit via event service client first
            if self.event_service_client:
                return self._emit_via_event_service(event)
            
            # Fallback to Redis queue
            if self.redis_client:
                return self._emit_via_redis(event)
            
            # Log event if no emission method available
            logger.warning(f"No event emission method available, logging event: {event['event_type']}")
            return True
            
        except Exception as e:
            logger.error(f"Error emitting event: {e}")
            return False
    
    def _emit_via_event_service(self, event: Dict[str, Any]) -> bool:
        """Emit event via event service client"""
        try:
            # Mock event service call - in real implementation, this would call actual service
            logger.info(f"Event emitted via event service: {event['event_type']}")
            return True
            
        except Exception as e:
            logger.error(f"Error emitting via event service: {e}")
            return False
    
    def _emit_via_redis(self, event: Dict[str, Any]) -> bool:
        """Emit event via Redis queue"""
        try:
            # Publish event to Redis queue
            queue_name = "bot_events"
            success = self.redis_client.publish_to_queue(queue_name, event)
            
            if success:
                logger.info(f"Event published to Redis queue: {event['event_type']}")
            else:
                logger.error(f"Failed to publish event to Redis queue: {event['event_type']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error emitting via Redis: {e}")
            return False
    
    def get_event_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get event history for a session"""
        try:
            # Mock event history - in real implementation, this would fetch from event store
            events = [
                {
                    "event_type": "session_created",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "event_type": "node_activated",
                    "session_id": session_id,
                    "node_name": "serve_categories",
                    "timestamp": datetime.now().isoformat()
                }
            ]
            
            return events[:limit]
            
        except Exception as e:
            logger.error(f"Error getting event history: {e}")
            return []
    
    def emit_custom_event(self, 
                         session_id: str, 
                         event_type: str, 
                         event_data: Dict[str, Any], 
                         metadata: Dict[str, Any] = None) -> bool:
        """Emit custom event"""
        try:
            event = {
                "event_type": event_type,
                "event_id": str(uuid.uuid4()),
                "session_id": session_id,
                "event_data": event_data,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            success = self._emit_event(event)
            if success:
                logger.info(f"Custom event emitted: {event_type} for session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error emitting custom event: {e}")
            return False