import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from models.node import IntentTree, NodeDefinition, NodeType, NodeHandler, NodeTransition, NodeValidation, ValidationRule
from utils.redis_client import RedisClient

logger = logging.getLogger(__name__)

class TreeLoader:
    """Load and manage intent trees from files or Redis"""
    
    def __init__(self, redis_client: RedisClient, trees_directory: str = "trees"):
        self.redis_client = redis_client
        self.trees_directory = Path(trees_directory)
        self.loaded_trees: Dict[str, IntentTree] = {}
    
    def load_tree_from_file(self, tree_name: str, file_path: str) -> Optional[IntentTree]:
        """Load intent tree from JSON file"""
        try:
            with open(file_path, 'r') as f:
                tree_data = json.load(f)
            
            return self._parse_tree_data(tree_name, tree_data)
        except Exception as e:
            logger.error(f"Failed to load tree from file: {e}")
            return None
    
    def load_tree_from_redis(self, tree_name: str) -> Optional[IntentTree]:
        """Load intent tree from Redis"""
        try:
            tree_data = self.redis_client.get_intent_tree(tree_name)
            if not tree_data:
                return None
            
            return self._parse_tree_data(tree_name, tree_data)
        except Exception as e:
            logger.error(f"Failed to load tree from Redis: {e}")
            return None
    
    def _parse_tree_data(self, tree_name: str, tree_data: Dict[str, Any]) -> IntentTree:
        """Parse tree data into IntentTree object"""
        nodes = {}
        
        for node_name, node_data in tree_data.get("nodes", {}).items():
            # Parse node definition
            node_def = NodeDefinition(
                node_name=node_name,
                node_type=NodeType(node_data["node_type"]),
                description=node_data["description"],
                handler=NodeHandler(
                    handler_function=node_data["handler"]["function"],
                    handler_module=node_data["handler"]["module"],
                    required_params=node_data["handler"].get("required_params", []),
                    optional_params=node_data["handler"].get("optional_params", [])
                ),
                validation_rules=self._parse_validation_rules(node_data.get("validation_rules", [])),
                allowed_transitions=self._parse_transitions(node_data.get("allowed_transitions", [])),
                timeout_seconds=node_data.get("timeout_seconds"),
                retry_count=node_data.get("retry_count", 0),
                is_async=node_data.get("is_async", False),
                response_template=node_data.get("response_template"),
                response_data=node_data.get("response_data", {}),
                is_active=node_data.get("is_active", True)
            )
            
            nodes[node_name] = node_def
        
        return IntentTree(
            tree_name=tree_name,
            root_node=tree_data["root_node"],
            nodes=nodes,
            description=tree_data.get("description", ""),
            version=tree_data.get("version", "1.0"),
            max_depth=tree_data.get("max_depth", 10),
            timeout_seconds=tree_data.get("timeout_seconds", 3600),
            is_active=tree_data.get("is_active", True)
        )
    
    def _parse_validation_rules(self, rules_data: List[Dict[str, Any]]) -> List[NodeValidation]:
        """Parse validation rules from data"""
        rules = []
        for rule_data in rules_data:
            rule = NodeValidation(
                rule_type=ValidationRule(rule_data["rule_type"]),
                field=rule_data["field"],
                condition=rule_data.get("condition"),
                error_message=rule_data.get("error_message")
            )
            rules.append(rule)
        return rules
    
    def _parse_transitions(self, transitions_data: List[Dict[str, Any]]) -> List[NodeTransition]:
        """Parse transitions from data"""
        transitions = []
        for trans_data in transitions_data:
            transition = NodeTransition(
                from_node=trans_data["from_node"],
                to_node=trans_data["to_node"],
                condition=trans_data.get("condition"),
                required_data=trans_data.get("required_data", []),
                validation_rules=self._parse_validation_rules(trans_data.get("validation_rules", []))
            )
            transitions.append(transition)
        return transitions
    
    def get_tree(self, tree_name: str) -> Optional[IntentTree]:
        """Get tree from cache or load it"""
        if tree_name in self.loaded_trees:
            return self.loaded_trees[tree_name]
        
        # Try to load from Redis first
        tree = self.load_tree_from_redis(tree_name)
        if tree:
            self.loaded_trees[tree_name] = tree
            return tree
        
        # Try to load from file
        tree_file = self.trees_directory / f"{tree_name}.json"
        if tree_file.exists():
            tree = self.load_tree_from_file(tree_name, str(tree_file))
            if tree:
                self.loaded_trees[tree_name] = tree
                return tree
        
        return None
    
    def load_all_trees(self) -> Dict[str, IntentTree]:
        """Load all available trees"""
        trees = {}
        
        # Load from Redis
        # This would need to be implemented based on your Redis key pattern
        
        # Load from files
        if self.trees_directory.exists():
            for tree_file in self.trees_directory.glob("*.json"):
                tree_name = tree_file.stem
                tree = self.load_tree_from_file(tree_name, str(tree_file))
                if tree:
                    trees[tree_name] = tree
        
        self.loaded_trees.update(trees)
        return trees
    
    def store_tree_to_redis(self, tree: IntentTree) -> bool:
        """Store tree definition to Redis"""
        try:
            tree_data = {
                "tree_name": tree.tree_name,
                "root_node": tree.root_node,
                "description": tree.description,
                "version": tree.version,
                "max_depth": tree.max_depth,
                "timeout_seconds": tree.timeout_seconds,
                "is_active": tree.is_active,
                "nodes": self._serialize_nodes(tree.nodes)
            }
            
            return self.redis_client.store_intent_tree(tree.tree_name, tree_data)
        except Exception as e:
            logger.error(f"Failed to store tree to Redis: {e}")
            return False
    
    def _serialize_nodes(self, nodes: Dict[str, NodeDefinition]) -> Dict[str, Any]:
        """Serialize nodes for storage"""
        serialized = {}
        for node_name, node_def in nodes.items():
            serialized[node_name] = {
                "node_type": node_def.node_type.value,
                "description": node_def.description,
                "handler": {
                    "function": node_def.handler.handler_function,
                    "module": node_def.handler.handler_module,
                    "required_params": node_def.handler.required_params,
                    "optional_params": node_def.handler.optional_params
                },
                "validation_rules": [
                    {
                        "rule_type": rule.rule_type.value,
                        "field": rule.field,
                        "condition": rule.condition,
                        "error_message": rule.error_message
                    } for rule in node_def.validation_rules
                ],
                "allowed_transitions": [
                    {
                        "from_node": trans.from_node,
                        "to_node": trans.to_node,
                        "condition": trans.condition,
                        "required_data": trans.required_data,
                        "validation_rules": [
                            {
                                "rule_type": rule.rule_type.value,
                                "field": rule.field,
                                "condition": rule.condition,
                                "error_message": rule.error_message
                            } for rule in trans.validation_rules
                        ]
                    } for trans in node_def.allowed_transitions
                ],
                "timeout_seconds": node_def.timeout_seconds,
                "retry_count": node_def.retry_count,
                "is_async": node_def.is_async,
                "response_template": node_def.response_template,
                "response_data": node_def.response_data,
                "is_active": node_def.is_active
            }
        return serialized