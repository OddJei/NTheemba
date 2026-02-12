"""Execute a node and produce a reply."""

import logging
import importlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from models.node import NodeDefinition, NodeType
from models.session_context import SessionContext, NodeState, NodeStatus
from utils.redis_client import RedisClient
from utils.tree_selector import TreeSelector

logger = logging.getLogger(__name__)

class NodeExecutor:
    """Handles node execution and routing to appropriate handlers"""
    
    def __init__(self, redis_client: RedisClient, tree_selector: TreeSelector):
        self.redis_client = redis_client
        self.tree_selector = tree_selector
        self.handler_cache = {}
    
    def execute(self, 
                node: NodeDefinition, 
                session: SessionContext, 
                payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Execute a node and return result"""
        try:
            # Validate node before execution
            if not self._validate_node_for_execution(node, session):
                return False, {}, ["Node validation failed"]
            
            # Route to appropriate handler
            handler_result = self._route_to_handler(node, session, payload)
            if not handler_result["success"]:
                return False, {}, handler_result["errors"]
            
            # Process execution result
            execution_result = self._process_execution_result(handler_result, node, session)
            
            # Update node state
            self._update_node_state(node, session, execution_result["success"])
            
            return execution_result["success"], execution_result["data"], execution_result["errors"]
            
        except Exception as e:
            logger.error(f"Error executing node {node.node_name}: {e}")
            return False, {}, [f"Execution error: {str(e)}"]
    
    def _validate_node_for_execution(self, node: NodeDefinition, session: SessionContext) -> bool:
        """Validate node before execution"""
        try:
            # Check if node is active
            if not node.is_active:
                logger.warning(f"Node {node.node_name} is not active")
                return False
            
            # Check session status
            if not session.is_active():
                logger.warning(f"Session {session.session_id} is not active")
                return False
            
            # Check node timeout
            if node.timeout_seconds and self._is_node_timed_out(node, session):
                logger.warning(f"Node {node.node_name} has timed out")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating node: {e}")
            return False
    
    def _is_node_timed_out(self, node: NodeDefinition, session: SessionContext) -> bool:
        """Check if node has timed out"""
        if not session.tree_state:
            return False
        
        current_node_state = session.tree_state.get_current_node_state()
        if not current_node_state:
            return False
        
        time_since_activation = datetime.now() - current_node_state.activated_at
        return time_since_activation.total_seconds() > node.timeout_seconds
    
    def _route_to_handler(self, 
                         node: NodeDefinition, 
                         session: SessionContext, 
                         payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route execution to appropriate handler based on session mode and node"""
        try:
            # Determine handler path
            handler_path = self._get_handler_path(node, session, payload)
            if not handler_path:
                return {
                    "success": False,
                    "errors": [f"No handler found for node {node.node_name}"],
                    "data": {}
                }
            
            # Import and execute handler
            handler_result = self._execute_handler(handler_path, node, session, payload)
            return handler_result
            
        except Exception as e:
            logger.error(f"Error routing to handler: {e}")
            return {
                "success": False,
                "errors": [f"Routing error: {str(e)}"],
                "data": {}
            }
    
    def _get_handler_path(self, node: NodeDefinition, session: SessionContext, payload: Dict[str, Any]) -> Optional[str]:
        """Get handler path based on session mode, user role, and intent/feature"""
        try:
            # Get session mode and user role
            session_mode = self._get_session_mode(session)
            user_role = self._get_user_role(session)
            
            # Get intent/feature from payload
            intent_feature = self.tree_selector._extract_intent_feature(payload)
            
            # Build handler path with intent/feature consideration
            if session_mode == "public":
                # Public mode handlers organized by feature
                if intent_feature == "catalog_browse":
                    handler_path = f"handlers.public_mode.catalog_browse.{node.handler.handler_function}"
                elif intent_feature == "order":
                    handler_path = f"handlers.public_mode.order.{node.handler.handler_function}"
                elif intent_feature == "registration":
                    handler_path = f"handlers.public_mode.registration.{node.handler.handler_function}"
                elif intent_feature == "help":
                    handler_path = f"handlers.public_mode.help.{node.handler.handler_function}"
                else:
                    # Default to catalog_browse for public mode
                    handler_path = f"handlers.public_mode.catalog_browse.{node.handler.handler_function}"
                    
            elif session_mode == "registered":
                if user_role == "msme":
                    if intent_feature == "product_management":
                        handler_path = f"handlers.registered_mode.msme.product_management.{node.handler.handler_function}"
                    elif intent_feature == "analytics_dashboard":
                        handler_path = f"handlers.registered_mode.msme.analytics_dashboard.{node.handler.handler_function}"
                    elif intent_feature == "profile_management":
                        handler_path = f"handlers.registered_mode.msme.profile_management.{node.handler.handler_function}"
                    elif intent_feature == "order_management":
                        handler_path = f"handlers.registered_mode.msme.order_management.{node.handler.handler_function}"
                    else:
                        handler_path = f"handlers.registered_mode.msme.product_management.{node.handler.handler_function}"
                        
                elif user_role == "affiliate":
                    if intent_feature == "catalog_browse":
                        handler_path = f"handlers.registered_mode.affiliate.catalog_browse.{node.handler.handler_function}"
                    elif intent_feature == "commission_tracking":
                        handler_path = f"handlers.registered_mode.affiliate.commission_tracking.{node.handler.handler_function}"
                    else:
                        handler_path = f"handlers.registered_mode.affiliate.catalog_browse.{node.handler.handler_function}"
                else:
                    # Default to public handlers for unknown roles
                    handler_path = f"handlers.public_mode.catalog_browse.{node.handler.handler_function}"
            else:
                # Default to public handlers
                handler_path = f"handlers.public_mode.catalog_browse.{node.handler.handler_function}"
            
            return handler_path
            
        except Exception as e:
            logger.error(f"Error getting handler path: {e}")
            return None
    
    def _get_session_mode(self, session: SessionContext) -> str:
        """Get session mode from session context"""
        # This would be determined based on your session logic
        # For now, return a default based on user context
        if session.user_context.business_id:
            return "registered"
        elif session.user_context.affiliate_id:
            return "registered"
        else:
            return "public"
    
    def _get_user_role(self, session: SessionContext) -> str:
        """Get user role from session context"""
        if session.user_context.business_id:
            return "msme"
        elif session.user_context.affiliate_id:
            return "affiliate"
        else:
            return "customer"
    
    def _execute_handler(self, 
                        handler_path: str, 
                        node: NodeDefinition, 
                        session: SessionContext, 
                        payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the handler function"""
        try:
            # Parse handler path
            module_path, function_name = handler_path.rsplit('.', 1)
            
            # Import module
            if handler_path in self.handler_cache:
                handler_module = self.handler_cache[handler_path]
            else:
                handler_module = importlib.import_module(module_path)
                self.handler_cache[handler_path] = handler_module
            
            # Get handler function
            handler_function = getattr(handler_module, function_name, None)
            if not handler_function:
                return {
                    "success": False,
                    "errors": [f"Handler function {function_name} not found in {module_path}"],
                    "data": {}
                }
            
            # Prepare handler parameters
            handler_params = self._prepare_handler_params(node, session, payload)
            
            # Execute handler
            if node.is_async:
                # For async handlers, you would need to handle this differently
                result = handler_function(**handler_params)
            else:
                result = handler_function(**handler_params)
            
            # Process result
            if isinstance(result, dict):
                return {
                    "success": True,
                    "data": result,
                    "errors": []
                }
            else:
                return {
                    "success": True,
                    "data": {"result": result},
                    "errors": []
                }
                
        except ImportError as e:
            logger.error(f"Failed to import handler module: {e}")
            return {
                "success": False,
                "errors": [f"Handler module not found: {str(e)}"],
                "data": {}
            }
        except Exception as e:
            logger.error(f"Error executing handler: {e}")
            return {
                "success": False,
                "errors": [f"Handler execution error: {str(e)}"],
                "data": {}
            }
    
    def _prepare_handler_params(self, 
                               node: NodeDefinition, 
                               session: SessionContext, 
                               payload: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare parameters for handler function"""
        params = {
            "session_id": session.session_id,
            "payload": payload,
            "node_name": node.node_name,
            "session_context": session
        }
        
        # Add required parameters
        for param in node.handler.required_params:
            if param == "user_id":
                params[param] = session.user_id
            elif param == "business_id":
                params[param] = session.user_context.business_id
            elif param == "affiliate_id":
                params[param] = session.user_context.affiliate_id
            elif param == "cart_items":
                params[param] = session.user_context.cart_items
            elif param == "current_order":
                params[param] = session.user_context.current_order
            else:
                # Try to get from payload data
                params[param] = payload.get("data", {}).get(param)
        
        # Add optional parameters
        for param in node.handler.optional_params:
            if param not in params:
                params[param] = payload.get("data", {}).get(param)
        
        return params
    
    def _process_execution_result(self, 
                                 handler_result: Dict[str, Any], 
                                 node: NodeDefinition, 
                                 session: SessionContext) -> Dict[str, Any]:
        """Process the result from handler execution"""
        try:
            if not handler_result["success"]:
                return {
                    "success": False,
                    "data": {},
                    "errors": handler_result["errors"]
                }
            
            # Extract data from handler result
            data = handler_result.get("data", {})
            
            # Apply response template if configured
            if node.response_template:
                data["template"] = node.response_template
            
            # Add response data
            if node.response_data:
                data.update(node.response_data)
            
            # Update session context if needed
            self._update_session_from_result(data, session)
            
            return {
                "success": True,
                "data": data,
                "errors": []
            }
            
        except Exception as e:
            logger.error(f"Error processing execution result: {e}")
            return {
                "success": False,
                "data": {},
                "errors": [f"Result processing error: {str(e)}"]
            }
    
    def _update_session_from_result(self, data: Dict[str, Any], session: SessionContext):
        """Update session context based on handler result"""
        try:
            # Update cart items if provided
            if "cart_items" in data:
                session.user_context.cart_items = data["cart_items"]
            
            # Update current order if provided
            if "current_order" in data:
                session.user_context.current_order = data["current_order"]
            
            # Update custom data
            if "session_data" in data:
                session.session_data.update(data["session_data"])
            
            # Save updated session
            self.redis_client.update_session(session)
            
        except Exception as e:
            logger.error(f"Error updating session from result: {e}")
    
    def _update_node_state(self, 
                          node: NodeDefinition, 
                          session: SessionContext, 
                          success: bool):
        """Update node state after execution"""
        try:
            if not session.tree_state:
                return
            
            # Find current node state
            current_node_state = session.tree_state.get_current_node_state()
            if current_node_state:
                # Update status
                current_node_state.status = NodeStatus.COMPLETED if success else NodeStatus.FAILED
                current_node_state.completed_at = datetime.now()
                
                # Update in Redis
                self.redis_client._store_tree_state(session.session_id, session.tree_state)
            
        except Exception as e:
            logger.error(f"Error updating node state: {e}")
    
    def execute_node(self, 
                    node_name: str, 
                    session: SessionContext, 
                    payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Main method to execute a node by name"""
        try:
            # Get node definition from tree
            # This would need to be implemented based on your tree loading logic
            # For now, return a placeholder
            return False, {}, [f"Node execution not fully implemented for {node_name}"]
            
        except Exception as e:
            logger.error(f"Error executing node {node_name}: {e}")
            return False, {}, [f"Node execution error: {str(e)}"]
