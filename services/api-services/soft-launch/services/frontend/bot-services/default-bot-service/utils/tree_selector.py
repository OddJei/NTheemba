"""Tree selector utility for determining correct tree structure based on mode and intent/feature."""

import logging
from typing import Dict, Any, Optional, List, Tuple
from models.node import IntentTree
from models.session_context import SessionContext
from utils.redis_client import RedisClient
from utils.tree_loader import TreeLoader

logger = logging.getLogger(__name__)

class TreeSelector:
    """Selects appropriate tree structure based on mode, role, and intent/feature"""
    
    def __init__(self, redis_client: RedisClient, tree_loader: TreeLoader):
        self.redis_client = redis_client
        self.tree_loader = tree_loader
        
        # Tree structure mapping: mode -> intent/feature -> tree_name
        self.tree_mapping = {
            "public": {
                "catalog_browse": "public_catalog_tree",
                "order": "public_order_tree", 
                "registration": "public_registration_tree",
                "help": "public_help_tree",
                "default": "public_catalog_tree"
            },
            "registered": {
                "msme": {
                    "product_management": "msme_product_tree",
                    "analytics_dashboard": "msme_analytics_tree",
                    "profile_management": "msme_profile_tree",
                    "order_management": "msme_order_tree",
                    "default": "msme_product_tree"
                },
                "affiliate": {
                    "catalog_browse": "affiliate_catalog_tree",
                    "commission_tracking": "affiliate_commission_tree",
                    "default": "affiliate_catalog_tree"
                }
            }
        }
    
    def select_tree(self, 
                   session: SessionContext, 
                   payload: Dict[str, Any]) -> Tuple[bool, Optional[IntentTree], List[str]]:
        """Select appropriate tree based on session mode, user role, and intent/feature"""
        try:
            # Get session mode
            session_mode = self._get_session_mode(session)
            
            # Get user role (for registered mode)
            user_role = self._get_user_role(session) if session_mode == "registered" else None
            
            # Get intent/feature from payload
            intent_feature = self._extract_intent_feature(payload)
            
            # Determine tree name
            tree_name = self._determine_tree_name(session_mode, user_role, intent_feature)
            if not tree_name:
                return False, None, [f"No tree found for mode={session_mode}, role={user_role}, feature={intent_feature}"]
            
            # Load tree
            tree = self._load_tree(tree_name)
            if not tree:
                return False, None, [f"Failed to load tree: {tree_name}"]
            
            # Update session with selected tree
            self._update_session_tree(session, tree_name, tree)
            
            logger.info(f"Selected tree '{tree_name}' for session {session.session_id}")
            return True, tree, []
            
        except Exception as e:
            logger.error(f"Error selecting tree: {e}")
            return False, None, [f"Tree selection error: {str(e)}"]
    
    def _get_session_mode(self, session: SessionContext) -> str:
        """Get session mode from session context"""
        # Check if user has business or affiliate context
        if session.user_context.business_id or session.user_context.affiliate_id:
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
            # Default fallback - should not happen in registered mode
            return "msme"
    
    def _extract_intent_feature(self, payload: Dict[str, Any]) -> str:
        """Extract intent/feature directly from payload intent"""
        try:
            # Get intent directly from payload - this should be the feature/tree name
            intent = payload.get("intent", "")
            
            # If intent is a dict, get the resolved_intent
            if isinstance(intent, dict):
                intent = intent.get("resolved_intent", "")
            
            # Use intent directly as feature name (e.g., "order", "registration", "analytics_dashboard")
            # Clean up the intent name if needed
            feature = intent.strip()
            
            # If no intent found, try to infer from context
            if not feature or feature == "":
                feature = self._infer_feature_from_context(payload)
            
            return feature
            
        except Exception as e:
            logger.error(f"Error extracting intent feature: {e}")
            return "default"
    
    def _infer_feature_from_context(self, payload: Dict[str, Any]) -> str:
        """Infer feature from payload context when intent is not clear"""
        try:
            # Check for specific keywords in message
            message = payload.get("message", {}).get("text", "").lower()
            
            if any(word in message for word in ["product", "catalog", "browse", "view"]):
                return "catalog_browse"
            elif any(word in message for word in ["order", "buy", "purchase", "checkout"]):
                return "order"
            elif any(word in message for word in ["register", "signup", "join"]):
                return "registration"
            elif any(word in message for word in ["help", "support", "assist"]):
                return "help"
            else:
                return "default"
                
        except Exception as e:
            logger.error(f"Error inferring feature: {e}")
            return "default"
    
    def _determine_tree_name(self, 
                           session_mode: str, 
                           user_role: Optional[str], 
                           intent_feature: str) -> Optional[str]:
        """Determine tree name based on mode, role, and feature"""
        try:
            if session_mode == "public":
                return self.tree_mapping["public"].get(intent_feature, "public_catalog_tree")
            
            elif session_mode == "registered" and user_role:
                role_mapping = self.tree_mapping["registered"].get(user_role, {})
                return role_mapping.get(intent_feature, role_mapping.get("default"))
            
            return None
            
        except Exception as e:
            logger.error(f"Error determining tree name: {e}")
            return None
    
    def _load_tree(self, tree_name: str) -> Optional[IntentTree]:
        """Load tree from Redis or file"""
        try:
            # Try to load from Redis first
            tree_data = self.redis_client.get_intent_tree(tree_name)
            if tree_data:
                # Convert Redis data to IntentTree object
                return self.tree_loader.load_from_redis_data(tree_data)
            
            # Fallback to file loading
            return self.tree_loader.load_tree(tree_name)
            
        except Exception as e:
            logger.error(f"Error loading tree {tree_name}: {e}")
            return None
    
    def _update_session_tree(self, session: SessionContext, tree_name: str, tree: IntentTree):
        """Update session with selected tree information"""
        try:
            # Update session data with tree information
            session.session_data.update({
                "current_tree": tree_name,
                "tree_version": tree.version,
                "tree_updated_at": tree.updated_at.isoformat()
            })
            
            # Update tree state if exists
            if session.tree_state:
                session.tree_state.tree_name = tree_name
            else:
                # Create new tree state
                from models.session_context import TreeState
                session.tree_state = TreeState(
                    tree_name=tree_name,
                    current_node=tree.root_node,
                    root_node=tree.root_node
                )
            
            # Save updated session
            self.redis_client.update_session(session)
            
        except Exception as e:
            logger.error(f"Error updating session tree: {e}")
    
    def get_available_trees(self, session_mode: str, user_role: Optional[str] = None) -> List[str]:
        """Get list of available trees for given mode and role"""
        try:
            if session_mode == "public":
                return list(self.tree_mapping["public"].keys())
            
            elif session_mode == "registered" and user_role:
                role_mapping = self.tree_mapping["registered"].get(user_role, {})
                return list(role_mapping.keys())
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting available trees: {e}")
            return []
    
    def switch_tree(self, 
                   session: SessionContext, 
                   new_intent_feature: str) -> Tuple[bool, Optional[IntentTree], List[str]]:
        """Switch to different tree for same session"""
        try:
            # Get current session mode and role
            session_mode = self._get_session_mode(session)
            user_role = self._get_user_role(session) if session_mode == "registered" else None
            
            # Determine new tree name
            tree_name = self._determine_tree_name(session_mode, user_role, new_intent_feature)
            if not tree_name:
                return False, None, [f"No tree found for feature: {new_intent_feature}"]
            
            # Load new tree
            tree = self._load_tree(tree_name)
            if not tree:
                return False, None, [f"Failed to load tree: {tree_name}"]
            
            # Update session with new tree
            self._update_session_tree(session, tree_name, tree)
            
            # Reset to root node of new tree
            session.set_current_node(tree.root_node)
            self.redis_client.update_current_node(session.session_id, tree.root_node)
            
            logger.info(f"Switched to tree '{tree_name}' for session {session.session_id}")
            return True, tree, []
            
        except Exception as e:
            logger.error(f"Error switching tree: {e}")
            return False, None, [f"Tree switch error: {str(e)}"]
