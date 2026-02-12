"""Manage progression through a decision tree for the bot."""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from models.node import NodeDefinition, IntentTree, NodeType, NodeTransition
from models.session_context import SessionContext, TreeState, NodeState, NodeStatus
from utils.redis_client import RedisClient
from utils.node_validator import NodeValidator
from utils.tree_loader import TreeLoader
from utils.tree_selector import TreeSelector

logger = logging.getLogger(__name__)

class TreeProgression:
    """Handles tree progression logic and node transitions"""
    
    def __init__(self, redis_client: RedisClient, tree_loader: TreeLoader, node_validator: NodeValidator, tree_selector: TreeSelector):
        self.redis_client = redis_client
        self.tree_loader = tree_loader
        self.node_validator = node_validator
        self.tree_selector = tree_selector
    
    def validate_current_node(self, session: SessionContext, intent_tree: IntentTree) -> Tuple[bool, Optional[str]]:
        """Validate current node and ensure it exists in the tree"""
        try:
            current_node_name = session.get_current_node()
            
            if not current_node_name:
                logger.warning(f"No current node found for session {session.session_id}")
                return False, "No current node found"
            
            # Check if current node exists in tree
            current_node = intent_tree.get_node(current_node_name)
            if not current_node:
                logger.error(f"Current node '{current_node_name}' not found in tree")
                return False, f"Node '{current_node_name}' not found in tree"
            
            # Check if node is active
            if not current_node.is_active:
                logger.warning(f"Current node '{current_node_name}' is not active")
                return False, f"Node '{current_node_name}' is not active"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating current node: {e}")
            return False, f"Validation error: {str(e)}"
    
    def determine_next_node(self, 
                          session: SessionContext, 
                          intent_tree: IntentTree, 
                          payload: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        """Determine the next node based on current state and payload"""
        try:
            current_node_name = session.get_current_node()
            if not current_node_name:
                return None, ["No current node found"]
            
            current_node = intent_tree.get_node(current_node_name)
            if not current_node:
                return None, [f"Current node '{current_node_name}' not found"]
            
            # Get user input and intent from payload
            user_input = payload.get("message", {}).get("text", "")
            intent = payload.get("intent", {})
            resolved_intent = intent.get("resolved_intent", "")
            
            # Determine next node based on intent and current node
            next_node_name = self._resolve_next_node(current_node, resolved_intent, user_input, payload)
            
            if not next_node_name:
                return None, [f"No valid next node found for intent '{resolved_intent}'"]
            
            # Validate the transition
            next_node = intent_tree.get_node(next_node_name)
            if not next_node:
                return None, [f"Target node '{next_node_name}' not found"]
            
            # Get current data for validation
            current_data = self._get_current_data(session, payload)
            
            # Validate transition
            is_valid, errors = self.node_validator.validate_transition(
                current_node, next_node, current_data, session.tree_state
            )
            
            if not is_valid:
                return None, errors
            
            return next_node_name, []
            
        except Exception as e:
            logger.error(f"Error determining next node: {e}")
            return None, [f"Error: {str(e)}"]
    
    def _resolve_next_node(self, 
                          current_node: NodeDefinition, 
                          intent: str, 
                          user_input: str, 
                          payload: Dict[str, Any]) -> Optional[str]:
        """Resolve next node based on intent and current node"""
        
        # Intent-based routing
        intent_mapping = {
            "browse_catalog": "serve_categories",
            "view_products": "serve_products", 
            "add_to_cart": "add_to_cart",
            "view_cart": "view_cart",
            "place_order": "confirm_cart",
            "register": "start_registration",
            "login": "authenticate_user",
            "help": "show_help",
            "back": self._get_previous_node,
            "restart": "root"
        }
        
        # Check for direct intent mapping
        if intent in intent_mapping:
            target = intent_mapping[intent]
            if callable(target):
                return target(current_node, payload)
            return target
        
        # Check allowed transitions for current node
        for transition in current_node.allowed_transitions:
            if self._matches_transition_condition(transition, intent, user_input, payload):
                return transition.to_node
        
        # Default fallback - check for any valid transition
        if current_node.allowed_transitions:
            return current_node.allowed_transitions[0].to_node
        
        return None
    
    def _get_previous_node(self, current_node: NodeDefinition, payload: Dict[str, Any]) -> Optional[str]:
        """Get previous node from history"""
        # This would need to be implemented based on your history tracking
        # For now, return a default fallback
        return "root"
    
    def _matches_transition_condition(self, 
                                    transition: NodeTransition, 
                                    intent: str, 
                                    user_input: str, 
                                    payload: Dict[str, Any]) -> bool:
        """Check if transition condition matches current context"""
        if not transition.condition:
            return True
        
        # Evaluate condition with current context
        context = {
            "intent": intent,
            "user_input": user_input,
            "payload": payload,
            "data": payload.get("data", {})
        }
        
        try:
            return eval(transition.condition, {"__builtins__": {}}, context)
        except Exception as e:
            logger.error(f"Error evaluating transition condition: {e}")
            return False
    
    def _get_current_data(self, session: SessionContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get current data for validation"""
        data = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "channel": session.channel,
            "cart_items": session.user_context.cart_items,
            "current_order": session.user_context.current_order,
            "business_id": session.user_context.business_id,
            "affiliate_id": session.user_context.affiliate_id
        }
        
        # Add payload data
        data.update(payload.get("data", {}))
        
        return data
    
    def update_current_node(self, session: SessionContext, next_node_name: str) -> bool:
        """Update current node in Redis and session"""
        try:
            # Update in Redis
            success = self.redis_client.update_current_node(session.session_id, next_node_name)
            if not success:
                logger.error(f"Failed to update current node in Redis for session {session.session_id}")
                return False
            
            # Update session context
            session.set_current_node(next_node_name)
            
            # Add to node history
            if session.tree_state:
                node_state = NodeState(
                    node_name=next_node_name,
                    status=NodeStatus.ACTIVE,
                    activated_at=datetime.now()
                )
                session.tree_state.add_node_to_history(node_state)
                
                # Update tree state in Redis
                self.redis_client._store_tree_state(session.session_id, session.tree_state)
            
            logger.info(f"Updated current node to '{next_node_name}' for session {session.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating current node: {e}")
            return False
    
    def ensure_session_continuity(self, session: SessionContext) -> bool:
        """Ensure session continuity and extend TTL if needed"""
        try:
            # Check if session is still active
            if not session.is_active():
                logger.warning(f"Session {session.session_id} is not active")
                return False
            
            # Extend session TTL
            session.extend_session()
            
            # Update in Redis
            success = self.redis_client.update_session(session)
            if not success:
                logger.error(f"Failed to update session in Redis")
                return False
            
            logger.info(f"Extended session TTL for {session.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring session continuity: {e}")
            return False
    
    def select_and_load_tree(self, session: SessionContext, payload: Dict[str, Any]) -> Tuple[bool, Optional[IntentTree], List[str]]:
        """Select and load appropriate tree based on session and payload"""
        try:
            # Use tree selector to determine correct tree
            success, intent_tree, errors = self.tree_selector.select_tree(session, payload)
            if not success:
                return False, None, errors
            
            return True, intent_tree, []
            
        except Exception as e:
            logger.error(f"Error selecting tree: {e}")
            return False, None, [f"Tree selection error: {str(e)}"]
    
    def check_tree_switch_needed(self, session: SessionContext, payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if tree switch is needed based on intent/feature change"""
        try:
            # Get current tree from session
            current_tree = session.session_data.get("current_tree")
            if not current_tree:
                return True, "No current tree found"
            
            # Get new intent/feature
            intent_feature = self.tree_selector._extract_intent_feature(payload)
            
            # Get session mode and role
            session_mode = self.tree_selector._get_session_mode(session)
            user_role = self.tree_selector._get_user_role(session) if session_mode == "registered" else None
            
            # Determine expected tree name
            expected_tree = self.tree_selector._determine_tree_name(session_mode, user_role, intent_feature)
            
            # Check if tree switch is needed
            if current_tree != expected_tree:
                return True, f"Tree switch needed: {current_tree} -> {expected_tree}"
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking tree switch: {e}")
            return True, f"Tree switch check error: {str(e)}"
    
    def progress_to_next_node(self, 
                            session: SessionContext, 
                            payload: Dict[str, Any]) -> Tuple[bool, Optional[str], List[str]]:
        """Main method to progress to next node with tree selection"""
        try:
            # Step 1: Check if tree switch is needed
            switch_needed, switch_reason = self.check_tree_switch_needed(session, payload)
            if switch_needed:
                logger.info(f"Tree switch needed: {switch_reason}")
                # Switch to new tree
                success, intent_tree, errors = self.tree_selector.switch_tree(session, self.tree_selector._extract_intent_feature(payload))
                if not success:
                    return False, None, errors
            else:
                # Load current tree
                success, intent_tree, errors = self.select_and_load_tree(session, payload)
                if not success:
                    return False, None, errors
            
            # Step 2: Validate current node
            is_valid, error = self.validate_current_node(session, intent_tree)
            if not is_valid:
                return False, None, [error]
            
            # Step 3: Determine next node
            next_node_name, errors = self.determine_next_node(session, intent_tree, payload)
            if not next_node_name:
                return False, None, errors
            
            # Step 4: Update current node
            success = self.update_current_node(session, next_node_name)
            if not success:
                return False, None, ["Failed to update current node"]
            
            # Step 5: Ensure session continuity
            success = self.ensure_session_continuity(session)
            if not success:
                logger.warning(f"Failed to ensure session continuity for {session.session_id}")
            
            return True, next_node_name, []
            
        except Exception as e:
            logger.error(f"Error in tree progression: {e}")
            return False, None, [f"Progression error: {str(e)}"]
