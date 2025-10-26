import logging
from typing import Dict, Any, List, Optional
from models.payload import BotPayload, MetaInfo, CurrentEvent, SessionInfo, UserInfo

logger = logging.getLogger(__name__)

class PayloadValidator:
    """Validate incoming payloads"""
    
    def __init__(self):
        self.required_fields = {
            "request_id": str,
            "message": str,
            "to": str,
            "from": str,
            "meta": dict
        }
        
        self.meta_required_fields = {
            "platform": str,
            "bot": dict,
            "user": dict,
            "session": dict,
            "current_event": dict
        }
    
    def validate_payload(self, payload_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate complete payload structure"""
        errors = []
        
        # Validate top-level fields
        top_level_errors = self._validate_top_level_fields(payload_data)
        errors.extend(top_level_errors)
        
        if errors:
            return False, errors
        
        # Validate meta structure
        meta_errors = self._validate_meta_structure(payload_data.get("meta", {}))
        errors.extend(meta_errors)
        
        # Validate session mode and user role consistency
        consistency_errors = self._validate_mode_role_consistency(payload_data.get("meta", {}))
        errors.extend(consistency_errors)
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def _validate_top_level_fields(self, payload_data: Dict[str, Any]) -> List[str]:
        """Validate top-level required fields"""
        errors = []
        
        for field, field_type in self.required_fields.items():
            if field not in payload_data:
                errors.append(f"Missing required field: {field}")
            elif not isinstance(payload_data[field], field_type):
                errors.append(f"Field '{field}' must be of type {field_type.__name__}")
        
        return errors
    
    def _validate_meta_structure(self, meta_data: Dict[str, Any]) -> List[str]:
        """Validate meta structure"""
        errors = []
        
        for field, field_type in self.meta_required_fields.items():
            if field not in meta_data:
                errors.append(f"Missing required meta field: {field}")
            elif not isinstance(meta_data[field], field_type):
                errors.append(f"Meta field '{field}' must be of type {field_type.__name__}")
        
        # Validate session structure
        if "session" in meta_data:
            session_errors = self._validate_session_structure(meta_data["session"])
            errors.extend(session_errors)
        
        # Validate user structure
        if "user" in meta_data:
            user_errors = self._validate_user_structure(meta_data["user"])
            errors.extend(user_errors)
        
        # Validate current_event structure
        if "current_event" in meta_data:
            event_errors = self._validate_current_event_structure(meta_data["current_event"])
            errors.extend(event_errors)
        
        return errors
    
    def _validate_session_structure(self, session_data: Dict[str, Any]) -> List[str]:
        """Validate session structure"""
        errors = []
        required_session_fields = ["session_id", "session_mode", "bot_type"]
        
        for field in required_session_fields:
            if field not in session_data:
                errors.append(f"Missing required session field: {field}")
        
        # Validate session_mode values
        if "session_mode" in session_data:
            valid_modes = ["public", "registered"]
            if session_data["session_mode"] not in valid_modes:
                errors.append(f"Invalid session_mode. Must be one of: {valid_modes}")
        
        return errors
    
    def _validate_user_structure(self, user_data: Dict[str, Any]) -> List[str]:
        """Validate user structure"""
        errors = []
        
        # Validate user role consistency
        if "role" in user_data:
            valid_roles = ["public", "msme", "affiliate"]
            if user_data["role"] not in valid_roles:
                errors.append(f"Invalid user role. Must be one of: {valid_roles}")
        
        return errors
    
    def _validate_current_event_structure(self, event_data: Dict[str, Any]) -> List[str]:
        """Validate current_event structure"""
        errors = []
        required_event_fields = ["event_id", "timestamp", "status", "current_node"]
        
        for field in required_event_fields:
            if field not in event_data:
                errors.append(f"Missing required current_event field: {field}")
        
        # Validate status values
        if "status" in event_data:
            valid_statuses = ["pending", "processing", "completed", "failed"]
            if event_data["status"] not in valid_statuses:
                errors.append(f"Invalid event status. Must be one of: {valid_statuses}")
        
        return errors
    
    def _validate_mode_role_consistency(self, meta_data: Dict[str, Any]) -> List[str]:
        """Validate consistency between session mode and user role"""
        errors = []
        
        session_mode = meta_data.get("session", {}).get("session_mode")
        user_role = meta_data.get("user", {}).get("role")
        
        if session_mode == "public" and user_role != "public":
            errors.append("Public session mode requires user role to be 'public'")
        
        elif session_mode == "registered":
            if user_role not in ["msme", "affiliate"]:
                errors.append("Registered session mode requires user role to be 'msme' or 'affiliate'")
        
        return errors
    
    def validate_payload_for_node(self, payload: BotPayload, node_name: str) -> tuple[bool, List[str]]:
        """Validate payload for specific node execution"""
        errors = []
        
        # Check if current node matches
        if payload.current_node != node_name:
            errors.append(f"Payload current_node '{payload.current_node}' does not match expected node '{node_name}'")
        
        # Validate session is active
        if not payload.meta.session.session_id:
            errors.append("Session ID is required")
        
        # Validate user context based on mode
        if payload.is_registered_mode:
            if not payload.user_role:
                errors.append("User role is required for registered mode")
            elif payload.user_role not in ["msme", "affiliate"]:
                errors.append(f"Invalid user role '{payload.user_role}' for registered mode")
        
        return len(errors) == 0, errors