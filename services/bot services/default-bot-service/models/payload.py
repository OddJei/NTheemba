from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class BotInfo:
    """Bot information structure"""
    bot_id: str
    is_default: bool
    business: Dict[str, Any] = field(default_factory=dict)
    bot_owner: Dict[str, Any] = field(default_factory=dict)

@dataclass
class UserInfo:
    """User information structure"""
    user_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None  # "public", "msme", "affiliate"
    phone: Optional[str] = None

@dataclass
class SessionInfo:
    """Session information structure"""
    session_id: str
    session_mode: str  # "public" or "registered"
    bot_type: str
    current_node: Optional[str] = None
    platform: str = "wa"

@dataclass
class PreviousEvent:
    """Previous event structure"""
    event_id: str
    message: str
    node: str

@dataclass
class CurrentEvent:
    """Current event structure"""
    event_id: str
    timestamp: str
    status: str
    current_node: str
    possible_next_nodes: Dict[str, str] = field(default_factory=dict)
    intent: Optional[str] = None
    next_node: Optional[str] = None
    intent_confidence: Optional[float] = None
    node_executed: Optional[str] = None
    action_status: Optional[str] = None
    tree_state: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MetaInfo:
    """Meta information structure"""
    platform: str
    bot: BotInfo
    user: UserInfo
    session: SessionInfo
    previous_events: List[PreviousEvent] = field(default_factory=list)
    current_event: CurrentEvent = None

@dataclass
class BotPayload:
    """Main payload structure matching your example"""
    request_id: str
    message: str
    to: str
    from_: str
    meta: MetaInfo
    
    @property
    def session_mode(self) -> str:
        """Get session mode from meta"""
        return self.meta.session.session_mode
    
    @property
    def user_role(self) -> Optional[str]:
        """Get user role"""
        return self.meta.user.role
    
    @property
    def current_node(self) -> Optional[str]:
        """Get current node"""
        return self.meta.session.current_node
    
    @property
    def session_id(self) -> str:
        """Get session ID"""
        return self.meta.session.session_id
    
    @property
    def is_public_mode(self) -> bool:
        """Check if in public mode"""
        return self.session_mode == "public"
    
    @property
    def is_registered_mode(self) -> bool:
        """Check if in registered mode"""
        return self.session_mode == "registered"
    
    @property
    def is_msme_user(self) -> bool:
        """Check if user is MSME"""
        return self.user_role == "msme"
    
    @property
    def is_affiliate_user(self) -> bool:
        """Check if user is affiliate"""
        return self.user_role == "affiliate"
    
    def get_tree_state(self) -> Dict[str, Any]:
        """Get current tree state"""
        if self.meta.current_event:
            return self.meta.current_event.tree_state
        return {}
    
    def set_tree_state(self, state: Dict[str, Any]):
        """Set tree state"""
        if self.meta.current_event:
            self.meta.current_event.tree_state = state
    
    def add_to_tree_state(self, key: str, value: Any):
        """Add to tree state"""
        if self.meta.current_event:
            self.meta.current_event.tree_state[key] = value
    
    def get_possible_next_nodes(self) -> Dict[str, str]:
        """Get possible next nodes"""
        if self.meta.current_event:
            return self.meta.current_event.possible_next_nodes
        return {}