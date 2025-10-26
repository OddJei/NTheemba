import logging
from typing import Dict, Any, List, Optional
from models.node import NodeDefinition, NodeTransition, ValidationRule, NodeValidation
from models.session_context import TreeState

logger = logging.getLogger(__name__)

class NodeValidator:
    """Validate node transitions and data"""
    
    def __init__(self):
        self.validation_cache = {}
    
    def validate_transition(self, 
                          from_node: NodeDefinition, 
                          to_node: NodeDefinition, 
                          current_data: Dict[str, Any],
                          tree_state: Optional[TreeState] = None) -> tuple[bool, List[str]]:
        """Validate transition from one node to another"""
        errors = []
        
        # Check if transition is allowed
        if not self._is_transition_allowed(from_node, to_node):
            errors.append(f"Transition from '{from_node.node_name}' to '{to_node.node_name}' is not allowed")
            return False, errors
        
        # Validate required data for target node
        data_errors = self._validate_required_data(to_node, current_data)
        errors.extend(data_errors)
        
        # Validate business rules
        business_errors = self._validate_business_rules(from_node, to_node, current_data, tree_state)
        errors.extend(business_errors)
        
        # Validate node-specific rules
        node_errors = self._validate_node_rules(to_node, current_data)
        errors.extend(node_errors)
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def _is_transition_allowed(self, from_node: NodeDefinition, to_node: NodeDefinition) -> bool:
        """Check if transition is explicitly allowed"""
        for transition in from_node.allowed_transitions:
            if transition.to_node == to_node.node_name:
                return True
        return False
    
    def _validate_required_data(self, node: NodeDefinition, data: Dict[str, Any]) -> List[str]:
        """Validate required data for node"""
        errors = []
        
        for rule in node.validation_rules:
            if rule.rule_type == ValidationRule.REQUIRED:
                if rule.field not in data or data[rule.field] is None:
                    error_msg = rule.error_message or f"Required field '{rule.field}' is missing"
                    errors.append(error_msg)
        
        return errors
    
    def _validate_business_rules(self, 
                                from_node: NodeDefinition, 
                                to_node: NodeDefinition, 
                                data: Dict[str, Any],
                                tree_state: Optional[TreeState]) -> List[str]:
        """Validate business-specific rules"""
        errors = []
        
        # Example business rules
        if to_node.node_name == "add_to_cart":
            if "product_id" not in data:
                errors.append("Product ID is required to add to cart")
            if "quantity" not in data or data["quantity"] <= 0:
                errors.append("Valid quantity is required")
        
        elif to_node.node_name == "place_order":
            if not data.get("cart_items"):
                errors.append("Cart must not be empty to place order")
            if not data.get("contact_info"):
                errors.append("Contact information is required")
            if not data.get("payment_method"):
                errors.append("Payment method must be selected")
        
        elif to_node.node_name == "generate_referral_links":
            if not data.get("product_id"):
                errors.append("Product ID is required for referral links")
        
        return errors
    
    def _validate_node_rules(self, node: NodeDefinition, data: Dict[str, Any]) -> List[str]:
        """Validate node-specific validation rules"""
        errors = []
        
        for rule in node.validation_rules:
            if not self._validate_rule(rule, data):
                error_msg = rule.error_message or f"Validation failed for field '{rule.field}'"
                errors.append(error_msg)
        
        return errors
    
    def _validate_rule(self, rule: NodeValidation, data: Dict[str, Any]) -> bool:
        """Validate individual rule"""
        try:
            if rule.rule_type == ValidationRule.REQUIRED:
                return rule.field in data and data[rule.field] is not None
            elif rule.rule_type == ValidationRule.CONDITIONAL:
                return self._evaluate_condition(rule.condition, data)
            elif rule.rule_type == ValidationRule.CUSTOM:
                return rule.custom_validator(data) if rule.custom_validator else True
            return True
        except Exception as e:
            logger.error(f"Rule validation error: {e}")
            return False
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """Evaluate condition string safely"""
        try:
            # Create safe evaluation context
            safe_context = {
                "data": data,
                "has": lambda key: key in data,
                "get": lambda key, default=None: data.get(key, default),
                "len": len
            }
            return eval(condition, {"__builtins__": {}}, safe_context)
        except Exception as e:
            logger.error(f"Condition evaluation error: {e}")
            return False
    
    def validate_tree_integrity(self, tree_name: str, nodes: Dict[str, NodeDefinition]) -> List[str]:
        """Validate overall tree integrity"""
        errors = []
        
        # Check for orphaned nodes
        referenced_nodes = set()
        for node_def in nodes.values():
            for transition in node_def.allowed_transitions:
                referenced_nodes.add(transition.to_node)
        
        for node_name in nodes.keys():
            if node_name not in referenced_nodes and node_name != "root":
                errors.append(f"Node '{node_name}' is not referenced by any transitions")
        
        # Check for circular references
        circular_errors = self._check_circular_references(nodes)
        errors.extend(circular_errors)
        
        return errors
    
    def _check_circular_references(self, nodes: Dict[str, NodeDefinition]) -> List[str]:
        """Check for circular references in tree"""
        errors = []
        
        for node_name, node_def in nodes.items():
            visited = set()
            if self._has_circular_path(node_name, node_def, nodes, visited):
                errors.append(f"Circular reference detected involving node '{node_name}'")
        
        return errors
    
    def _has_circular_path(self, 
                          current_node: str, 
                          node_def: NodeDefinition, 
                          all_nodes: Dict[str, NodeDefinition], 
                          visited: set) -> bool:
        """Check if there's a circular path from current node"""
        if current_node in visited:
            return True
        
        visited.add(current_node)
        
        for transition in node_def.allowed_transitions:
            next_node_name = transition.to_node
            if next_node_name in all_nodes:
                if self._has_circular_path(next_node_name, all_nodes[next_node_name], all_nodes, visited.copy()):
                    return True
        
        return False