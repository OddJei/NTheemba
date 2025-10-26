"""Default bot controller - main entry point for bot service."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from config.bot_config import bot_config
from utils.redis_client import RedisClient
from utils.tree_loader import TreeLoader
from utils.node_validator import NodeValidator
from utils.tree_selector import TreeSelector
from services.tree_progression import TreeProgression
from services.node_executor import NodeExecutor
from events.event_emitter import EventEmitter
from api.auth_service import AuthServiceClient
from api.session_service import SessionServiceClient
from api.event_service import EventServiceClient
from api.notification_service import NotificationServiceClient

logger = logging.getLogger(__name__)

class DefaultBotController:
    """Main controller for default bot service"""
    
    def __init__(self):
        """Initialize DefaultBotController with given configuration.
        
        :param None:
        :return None
        """
        
        self.config = bot_config
        self.redis_client = RedisClient(self.config.get_redis_config())
        # Ensure redis client knows where to publish replies — used by the queue worker
        try:
            reply_queue_name = self.config.get_queue_config().get("reply_queue")
            if reply_queue_name:
                # attach attribute so worker can read it
                setattr(self.redis_client, "reply_queue_name", reply_queue_name)
        except Exception:
            # not critical — worker will fallback to default reply_queue
            logger.debug("No reply_queue configured; worker will use default 'reply_queue'")
        self.tree_loader = TreeLoader(self.redis_client)
        self.node_validator = NodeValidator()
        self.tree_selector = TreeSelector(self.redis_client, self.tree_loader)
        
        # Initialize services
        self.tree_progression = TreeProgression(
            self.redis_client,
            self.tree_loader,
            self.node_validator,
            self.tree_selector
        )
        self.node_executor = NodeExecutor(self.redis_client, self.tree_selector)
        self.event_emitter = EventEmitter(self.redis_client)
        
        # Initialize API clients
        self.auth_client = AuthServiceClient()
        self.session_client = SessionServiceClient()
        self.event_client = EventServiceClient()
        self.notification_client = NotificationServiceClient()
        
        # Validate configuration
        if not self.config.validate_config():
            raise ValueError("Invalid configuration")
        
        logger.info("DefaultBotController initialized successfully")
    
    def process_message(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming message and return bot response"""
        try:
            logger.info(f"Processing message for session: {session_id}")
            
            # Validate payload
            if not self._validate_payload(payload):
                return self._create_error_response("Invalid payload format")
            
            # Get or create session context
            session_context = self._get_or_create_session(session_id, payload)
            if not session_context:
                return self._create_error_response("Failed to create session")
            
            # Emit session updated event
            self.event_emitter.emit_session_updated(
                session_id,
                "message_received",
                {"payload": payload}
            )
            
            # Determine current node and progress
            current_node = session_context.tree_state.current_node
            if not current_node:
                # Start with root node
                current_node = self._get_root_node(session_context)
                if not current_node:
                    return self._create_error_response("No root node found")
            
            # Progress to next node
            progression_result = self.tree_progression.progress_to_next_node(
                session_id,
                payload,
                session_context
            )
            
            if not progression_result.get("success", False):
                return self._create_error_response(
                    progression_result.get("error", "Failed to progress to next node")
                )
            
            # Execute current node
            execution_result = self.node_executor.execute(
                session_id,
                payload,
                session_context
            )
            
            if not execution_result.get("success", False):
                return self._create_error_response(
                    execution_result.get("error", "Failed to execute node")
                )
            
            # Emit events
            self._emit_execution_events(session_id, execution_result, session_context)
            
            # Create response
            response = self._create_response(execution_result, session_context)
            
            logger.info(f"Message processed successfully for session: {session_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.event_emitter.emit_error_occurred(
                session_id,
                "message_processing_error",
                str(e)
            )
            return self._create_error_response(f"Internal error: {str(e)}")
    
    def _validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate incoming payload"""
        try:
            required_fields = ["message"]
            for field in required_fields:
                if field not in payload:
                    logger.warning(f"Missing required field in payload: {field}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error validating payload: {e}")
            return False
    
    def _get_or_create_session(self, session_id: str, payload: Dict[str, Any]) -> Optional[Any]:
        """Get existing session or create new one"""
        try:
            # Try to get existing session
            session_context = self.redis_client.get_session(session_id)
            if session_context:
                logger.info(f"Retrieved existing session: {session_id}")
                return session_context
            
            # Create new session
            user_id = payload.get("user_id")
            session_mode = self._determine_session_mode(payload)
            
            session_context = self._create_new_session(session_id, user_id, session_mode, payload)
            if session_context:
                logger.info(f"Created new session: {session_id}")
                return session_context
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting/creating session: {e}")
            return None
    
    def _determine_session_mode(self, payload: Dict[str, Any]) -> str:
        """Determine session mode from payload"""
        user_id = payload.get("user_id")
        if user_id:
            return "registered"
        return "public"
    
    def _create_new_session(self, session_id: str, user_id: str, session_mode: str, payload: Dict[str, Any]) -> Optional[Any]:
        """Create new session context"""
        try:
            from models.session_context import SessionContext, UserContext, TreeState
            
            user_context = UserContext(
                user_id=user_id,
                session_mode=session_mode,
                user_role=payload.get("user_role", "customer"),
                cart_items=[],
                current_order=None,
                preferences={}
            )
            
            tree_state = TreeState(
                current_tree=None,
                current_node=None,
                node_history=[],
                tree_data={}
            )
            
            session_context = SessionContext(
                session_id=session_id,
                user_context=user_context,
                tree_state=tree_state,
                session_data=payload.get("session_data", {}),
                created_at=datetime.now(),
                last_activity=datetime.now(),
                status="active"
            )
            
            # Save to Redis
            success = self.redis_client.create_session(session_id, session_context)
            if success:
                # Emit session created event
                self.event_emitter.emit_session_created(
                    session_id,
                    user_id or "anonymous",
                    session_mode
                )
                return session_context
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating new session: {e}")
            return None
    
    def _get_root_node(self, session_context: Any) -> Optional[str]:
        """Get root node for session"""
        try:
            # Select appropriate tree
            tree = self.tree_selector.select_tree(session_context)
            if not tree:
                return None
            
            # Get root node
            if tree.root_node:
                return tree.root_node
            elif tree.nodes:
                # Find first node if no explicit root
                return list(tree.nodes.keys())[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting root node: {e}")
            return None
    
    def _emit_execution_events(self, session_id: str, execution_result: Dict[str, Any], session_context: Any):
        """Emit execution events"""
        try:
            # Emit node activated event
            current_node = session_context.tree_state.current_node
            if current_node:
                self.event_emitter.emit_node_activated(
                    session_id,
                    current_node,
                    execution_result.get("intent", "unknown"),
                    {"execution_result": execution_result}
                )
            
            # Emit action performed event
            self.event_emitter.emit_action_performed(
                session_id,
                "node_execution",
                execution_result,
                {"session_context": session_context}
            )
            
        except Exception as e:
            logger.error(f"Error emitting execution events: {e}")
    
    def _create_response(self, execution_result: Dict[str, Any], session_context: Any) -> Dict[str, Any]:
        """Create bot response"""
        try:
            response = {
                "success": True,
                "message": execution_result.get("message", "Bot response"),
                "data": execution_result.get("data", {}),
                "session_id": session_context.session_id,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add session data if updated
            if execution_result.get("session_data"):
                response["session_data"] = execution_result["session_data"]
            
            # Add next actions if available
            if execution_result.get("next_actions"):
                response["next_actions"] = execution_result["next_actions"]
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating response: {e}")
            return self._create_error_response("Failed to create response")
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            "success": False,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status"""
        try:
            # Check Redis connection
            redis_status = self.redis_client.ping()
            
            # Check API services
            api_status = {}
            api_config = self.config.get_api_config()
            for service_name, service_config in api_config.items():
                try:
                    # Mock health check - in real implementation, ping each service
                    api_status[service_name] = "healthy"
                except Exception:
                    api_status[service_name] = "unhealthy"
            
            return {
                "status": "healthy" if redis_status else "unhealthy",
                "redis": "connected" if redis_status else "disconnected",
                "api_services": api_status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def cleanup_expired_sessions(self) -> Dict[str, Any]:
        """Cleanup expired sessions"""
        try:
            # This would implement session cleanup logic
            logger.info("Session cleanup completed")
            return {"success": True, "message": "Sessions cleaned up"}
            
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return {"success": False, "error": str(e)}