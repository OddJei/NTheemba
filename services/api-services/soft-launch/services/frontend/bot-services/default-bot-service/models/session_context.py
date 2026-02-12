from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

class SessionStatus(Enum):
    """Session status enumeration"""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    COMPLETED = "completed"

class NodeStatus(Enum):
    """Node status enumeration"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class NodeState:
    """Individual node state"""
    node_name: str
    status: NodeStatus
    activated_at: datetime
    completed_at: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def is_completed(self) -> bool:
        return self.status == NodeStatus.COMPLETED
    
    def is_active(self) -> bool:
        return self.status == NodeStatus.ACTIVE

@dataclass
class TreeState:
    """Tree progression state"""
    tree_name: str
    current_node: str
    root_node: str
    node_history: List[NodeState] = field(default_factory=list)
    node_data: Dict[str, Any] = field(default_factory=dict)
    
    def add_node_to_history(self, node_state: NodeState):
        """Add node to history"""
        self.node_history.append(node_state)
    
    def get_node_data(self, node_name: str) -> Dict[str, Any]:
        """Get data for specific node"""
        return self.node_data.get(node_name, {})
    
    def set_node_data(self, node_name: str, data: Dict[str, Any]):
        """Set data for specific node"""
        self.node_data[node_name] = data
    
    def get_current_node_state(self) -> Optional[NodeState]:
        """Get current node state"""
        for node_state in reversed(self.node_history):
            if node_state.node_name == self.current_node:
                return node_state
        return None

@dataclass
class UserContext:
    """User-specific context data"""
    # Authentication
    is_authenticated: bool = False
    auth_token: Optional[str] = None
    otp_verified: bool = False
    
    # User preferences
    language: str = "en"
    timezone: str = "UTC"
    
    # Business context (for MSME)
    business_id: Optional[str] = None
    business_name: Optional[str] = None
    
    # Affiliate context
    affiliate_id: Optional[str] = None
    referral_code: Optional[str] = None
    
    # Cart and order context
    cart_items: List[Dict[str, Any]] = field(default_factory=list)
    current_order: Optional[Dict[str, Any]] = None
    
    # Custom data
    custom_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SessionContext:
    """Complete session context"""
    session_id: str
    user_id: Optional[str]
    status: SessionStatus
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    
    # Core context
    user_context: UserContext
    tree_state: Optional[TreeState] = None
    
    # Session metadata
    channel: str = "wa"
    device_info: Dict[str, Any] = field(default_factory=dict)
    session_data: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if session is active"""
        return self.status == SessionStatus.ACTIVE and datetime.now() < self.expires_at
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.now() >= self.expires_at
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    def extend_session(self, ttl_seconds: int = 3600):
        """Extend session expiration"""
        self.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
    
    def get_current_node(self) -> Optional[str]:
        """Get current node from tree state"""
        if self.tree_state:
            return self.tree_state.current_node
        return None
    
    def set_current_node(self, node_name: str):
        """Set current node in tree state"""
        if self.tree_state:
            self.tree_state.current_node = node_name
    
    def add_cart_item(self, item: Dict[str, Any]):
        """Add item to cart"""
        self.user_context.cart_items.append(item)
    
    def remove_cart_item(self, item_id: str):
        """Remove item from cart"""
        self.user_context.cart_items = [
            item for item in self.user_context.cart_items 
            if item.get('id') != item_id
        ]
    
    def clear_cart(self):
        """Clear all cart items"""
        self.user_context.cart_items.clear()