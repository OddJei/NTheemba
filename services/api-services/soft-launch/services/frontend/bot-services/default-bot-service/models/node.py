from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class NodeType(Enum):
    """Node type enumeration"""
    START = "start"
    ACTION = "action"
    DECISION = "decision"
    END = "end"
    CONDITIONAL = "conditional"

class ValidationRule(Enum):
    """Validation rule types"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"
    CUSTOM = "custom"

@dataclass
class NodeValidation:
    """Node validation rules"""
    rule_type: ValidationRule
    field: str
    condition: Optional[str] = None
    error_message: Optional[str] = None
    custom_validator: Optional[Callable] = None

@dataclass
class NodeTransition:
    """Node transition definition"""
    from_node: str
    to_node: str
    condition: Optional[str] = None
    required_data: List[str] = field(default_factory=list)
    validation_rules: List[NodeValidation] = field(default_factory=list)
    
    def is_valid_transition(self, current_data: Dict[str, Any]) -> bool:
        """Check if transition is valid based on current data"""
        # Check required data
        for required_field in self.required_data:
            if required_field not in current_data:
                return False
        
        # Check validation rules
        for rule in self.validation_rules:
            if not self._validate_rule(rule, current_data):
                return False
        
        return True
    
    def _validate_rule(self, rule: NodeValidation, data: Dict[str, Any]) -> bool:
        """Validate individual rule"""
        if rule.rule_type == ValidationRule.REQUIRED:
            return rule.field in data and data[rule.field] is not None
        elif rule.rule_type == ValidationRule.CONDITIONAL:
            return self._evaluate_condition(rule.condition, data)
        elif rule.rule_type == ValidationRule.CUSTOM:
            return rule.custom_validator(data) if rule.custom_validator else True
        return True
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """Evaluate condition string"""
        try:
            return eval(condition, {"data": data})
        except:
            return False

@dataclass
class NodeHandler:
    """Node handler definition"""
    handler_function: str  # Function name to call
    handler_module: str    # Module containing the function
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    
    def get_handler_path(self) -> str:
        """Get full handler path"""
        return f"{self.handler_module}.{self.handler_function}"

@dataclass
class NodeDefinition:
    """Complete node definition"""
    node_name: str
    node_type: NodeType
    description: str
    
    # Handler information
    handler: NodeHandler
    
    # Validation and transitions
    validation_rules: List[NodeValidation] = field(default_factory=list)
    allowed_transitions: List[NodeTransition] = field(default_factory=list)
    
    # Node metadata
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    is_async: bool = False
    
    # Response configuration
    response_template: Optional[str] = None
    response_data: Dict[str, Any] = field(default_factory=dict)
    
    # Node state
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
    def can_transition_to(self, target_node: str, current_data: Dict[str, Any]) -> bool:
        """Check if transition to target node is allowed"""
        for transition in self.allowed_transitions:
            if transition.to_node == target_node:
                return transition.is_valid_transition(current_data)
        return False
    
    def get_valid_transitions(self, current_data: Dict[str, Any]) -> List[str]:
        """Get list of valid transition targets"""
        valid_targets = []
        for transition in self.allowed_transitions:
            if transition.is_valid_transition(current_data):
                valid_targets.append(transition.to_node)
        return valid_targets
    
    def validate_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate data against node rules"""
        errors = []
        for rule in self.validation_rules:
            if not self._validate_rule(rule, data):
                error_msg = rule.error_message or f"Validation failed for {rule.field}"
                errors.append(error_msg)
        return errors
    
    def _validate_rule(self, rule: NodeValidation, data: Dict[str, Any]) -> bool:
        """Validate individual rule"""
        if rule.rule_type == ValidationRule.REQUIRED:
            return rule.field in data and data[rule.field] is not None
        elif rule.rule_type == ValidationRule.CONDITIONAL:
            return self._evaluate_condition(rule.condition, data)
        elif rule.rule_type == ValidationRule.CUSTOM:
            return rule.custom_validator(data) if rule.custom_validator else True
        return True
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """Evaluate condition string"""
        try:
            return eval(condition, {"data": data})
        except:
            return False

@dataclass
class IntentTree:
    """Complete intent tree definition"""
    tree_name: str
    root_node: str
    nodes: Dict[str, NodeDefinition]
    description: str
    
    # Tree metadata
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Tree configuration
    max_depth: int = 10
    timeout_seconds: int = 3600
    is_active: bool = True
    
    def get_node(self, node_name: str) -> Optional[NodeDefinition]:
        """Get node definition by name"""
        return self.nodes.get(node_name)
    
    def get_root_node(self) -> Optional[NodeDefinition]:
        """Get root node definition"""
        return self.get_node(self.root_node)
    
    def validate_tree(self) -> List[str]:
        """Validate tree structure"""
        errors = []
        
        # Check if root node exists
        if not self.get_root_node():
            errors.append(f"Root node '{self.root_node}' not found")
        
        # Check if all referenced nodes exist
        for node_name, node_def in self.nodes.items():
            for transition in node_def.allowed_transitions:
                if transition.to_node not in self.nodes:
                    errors.append(f"Node '{node_name}' references non-existent node '{transition.to_node}'")
        
        return errors
    
    def get_tree_path(self, from_node: str, to_node: str) -> List[str]:
        """Get path from one node to another"""
        # Simple BFS implementation to find path
        queue = [(from_node, [from_node])]
        visited = {from_node}
        
        while queue:
            current_node, path = queue.pop(0)
            
            if current_node == to_node:
                return path
            
            node_def = self.get_node(current_node)
            if node_def:
                for transition in node_def.allowed_transitions:
                    next_node = transition.to_node
                    if next_node not in visited:
                        visited.add(next_node)
                        queue.append((next_node, path + [next_node]))
        
        return []  # No path found