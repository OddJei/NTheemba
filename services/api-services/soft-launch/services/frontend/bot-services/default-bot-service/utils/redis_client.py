import redis
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import asdict
from models.session_context import SessionContext, SessionStatus, TreeState, NodeState, NodeStatus
from models.payload import BotPayload

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis client for session and tree state management"""
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None):
        """Initialize Redis connection"""
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
        self.default_ttl = 3600  # 1 hour default TTL
    
    def test_connection(self) -> bool:
        """Test Redis connection"""
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False
    
    # Session Management
    def create_session(self, session_context: SessionContext) -> bool:
        """Create new session in Redis"""
        try:
            session_key = f"session:{session_context.session_id}"
            session_data = {
                "session_id": session_context.session_id,
                "user_id": session_context.user_id,
                "status": session_context.status.value,
                "created_at": session_context.created_at.isoformat(),
                "last_activity": session_context.last_activity.isoformat(),
                "expires_at": session_context.expires_at.isoformat(),
                "channel": session_context.channel,
                "user_context": asdict(session_context.user_context),
                "session_data": session_context.session_data
            }
            
            # Store session with TTL
            ttl_seconds = int((session_context.expires_at - datetime.now()).total_seconds())
            self.redis_client.hset(session_key, mapping=session_data)
            self.redis_client.expire(session_key, ttl_seconds)
            
            # Store tree state if exists
            if session_context.tree_state:
                self._store_tree_state(session_context.session_id, session_context.tree_state)
            
            return True
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session from Redis"""
        try:
            session_key = f"session:{session_id}"
            session_data = self.redis_client.hgetall(session_key)
            
            if not session_data:
                return None
            
            # Reconstruct SessionContext
            session_context = SessionContext(
                session_id=session_data["session_id"],
                user_id=session_data.get("user_id"),
                status=SessionStatus(session_data["status"]),
                created_at=datetime.fromisoformat(session_data["created_at"]),
                last_activity=datetime.fromisoformat(session_data["last_activity"]),
                expires_at=datetime.fromisoformat(session_data["expires_at"]),
                channel=session_data.get("channel", "wa"),
                user_context=session_data.get("user_context", {}),
                session_data=json.loads(session_data.get("session_data", "{}"))
            )
            
            # Load tree state if exists
            tree_state = self._load_tree_state(session_id)
            if tree_state:
                session_context.tree_state = tree_state
            
            return session_context
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    def update_session(self, session_context: SessionContext) -> bool:
        """Update existing session"""
        try:
            session_key = f"session:{session_context.session_id}"
            
            # Update last activity
            session_context.update_activity()
            
            session_data = {
                "status": session_context.status.value,
                "last_activity": session_context.last_activity.isoformat(),
                "expires_at": session_context.expires_at.isoformat(),
                "user_context": json.dumps(asdict(session_context.user_context)),
                "session_data": json.dumps(session_context.session_data)
            }
            
            self.redis_client.hset(session_key, mapping=session_data)
            
            # Update tree state if exists
            if session_context.tree_state:
                self._store_tree_state(session_context.session_id, session_context.tree_state)
            
            return True
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis"""
        try:
            session_key = f"session:{session_id}"
            tree_key = f"tree_state:{session_id}"
            
            self.redis_client.delete(session_key)
            self.redis_client.delete(tree_key)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False
    
    # Tree State Management
    def _store_tree_state(self, session_id: str, tree_state: TreeState):
        """Store tree state in Redis"""
        try:
            tree_key = f"tree_state:{session_id}"
            tree_data = {
                "tree_name": tree_state.tree_name,
                "current_node": tree_state.current_node,
                "root_node": tree_state.root_node,
                "node_data": json.dumps(tree_state.node_data),
                "node_history": json.dumps([asdict(node) for node in tree_state.node_history])
            }
            
            self.redis_client.hset(tree_key, mapping=tree_data)
            self.redis_client.expire(tree_key, self.default_ttl)
        except Exception as e:
            logger.error(f"Failed to store tree state: {e}")
    
    def _load_tree_state(self, session_id: str) -> Optional[TreeState]:
        """Load tree state from Redis"""
        try:
            tree_key = f"tree_state:{session_id}"
            tree_data = self.redis_client.hgetall(tree_key)
            
            if not tree_data:
                return None
            
            # Reconstruct TreeState
            node_history_data = json.loads(tree_data.get("node_history", "[]"))
            node_history = []
            for node_data in node_history_data:
                node_history.append(NodeState(
                    node_name=node_data["node_name"],
                    status=NodeStatus(node_data["status"]),
                    activated_at=datetime.fromisoformat(node_data["activated_at"]),
                    completed_at=datetime.fromisoformat(node_data["completed_at"]) if node_data.get("completed_at") else None,
                    data=node_data.get("data", {}),
                    error_message=node_data.get("error_message")
                ))
            
            tree_state = TreeState(
                tree_name=tree_data["tree_name"],
                current_node=tree_data["current_node"],
                root_node=tree_data["root_node"],
                node_data=json.loads(tree_data.get("node_data", "{}")),
                node_history=node_history
            )
            
            return tree_state
        except Exception as e:
            logger.error(f"Failed to load tree state: {e}")
            return None
    
    def update_current_node(self, session_id: str, node_name: str) -> bool:
        """Update current node for session"""
        try:
            tree_key = f"tree_state:{session_id}"
            self.redis_client.hset(tree_key, "current_node", node_name)
            return True
        except Exception as e:
            logger.error(f"Failed to update current node: {e}")
            return False
    
    def get_current_node(self, session_id: str) -> Optional[str]:
        """Get current node for session"""
        try:
            tree_key = f"tree_state:{session_id}"
            return self.redis_client.hget(tree_key, "current_node")
        except Exception as e:
            logger.error(f"Failed to get current node: {e}")
            return None
    
    def set_node_data(self, session_id: str, node_name: str, data: Dict[str, Any]) -> bool:
        """Set data for specific node"""
        try:
            tree_key = f"tree_state:{session_id}"
            current_data = self.redis_client.hget(tree_key, "node_data")
            node_data = json.loads(current_data) if current_data else {}
            node_data[node_name] = data
            
            self.redis_client.hset(tree_key, "node_data", json.dumps(node_data))
            return True
        except Exception as e:
            logger.error(f"Failed to set node data: {e}")
            return False
    
    def get_node_data(self, session_id: str, node_name: str) -> Dict[str, Any]:
        """Get data for specific node"""
        try:
            tree_key = f"tree_state:{session_id}"
            current_data = self.redis_client.hget(tree_key, "node_data")
            node_data = json.loads(current_data) if current_data else {}
            return node_data.get(node_name, {})
        except Exception as e:
            logger.error(f"Failed to get node data: {e}")
            return {}
    
    # Intent Tree Management
    def store_intent_tree(self, tree_name: str, tree_data: Dict[str, Any]) -> bool:
        """Store intent tree definition"""
        try:
            tree_key = f"intent_tree:{tree_name}"
            self.redis_client.hset(tree_key, mapping=tree_data)
            return True
        except Exception as e:
            logger.error(f"Failed to store intent tree: {e}")
            return False
    
    def get_intent_tree(self, tree_name: str) -> Optional[Dict[str, Any]]:
        """Get intent tree definition"""
        try:
            tree_key = f"intent_tree:{tree_name}"
            return self.redis_client.hgetall(tree_key)
        except Exception as e:
            logger.error(f"Failed to get intent tree: {e}")
            return None
    
    # Queue Management
    def publish_to_queue(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish message to Redis queue"""
        try:
            self.redis_client.lpush(queue_name, json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Failed to publish to queue: {e}")
            return False
    
    def consume_from_queue(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Consume message from Redis queue"""
        try:
            result = self.redis_client.brpop(queue_name, timeout=timeout)
            if result:
                return json.loads(result[1])
            return None
        except Exception as e:
            logger.error(f"Failed to consume from queue: {e}")
            return None

    # Redis Streams helpers (optional advanced queueing)
    def xadd(self, stream_name: str, message: Dict[str, Any], maxlen: Optional[int] = None) -> Optional[str]:
        """Append an entry to a Redis stream. Returns message id."""
        try:
            # redis-py expects mapping of str->str
            mapping = {k: json.dumps(v) for k, v in message.items()}
            args = {}
            if maxlen:
                args["maxlen"] = maxlen
            return self.redis_client.xadd(stream_name, mapping, **args)
        except Exception as e:
            logger.error("Failed to xadd to stream %s: %s", stream_name, e)
            return None

    def ensure_consumer_group(self, stream_name: str, group_name: str):
        """Ensure consumer group exists for stream; create with '0' if missing."""
        try:
            groups = self.redis_client.xinfo_groups(stream_name)
            # if no exception, group exists check
            for g in groups:
                if g.get("name") == group_name:
                    return True
        except Exception:
            # xinfo_groups will raise if stream missing — create stream and group
            try:
                # create group on stream with ID 0 (from beginning)
                self.redis_client.xgroup_create(stream_name, group_name, id="0", mkstream=True)
                return True
            except Exception as e:
                logger.error("Failed to create consumer group %s on stream %s: %s", group_name, stream_name, e)
                return False

    def xreadgroup(self, stream_name: str, group_name: str, consumer_name: str, block_ms: int = 1000, count: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Read messages for a consumer group. Returns list of {id, data} dicts."""
        try:
            res = self.redis_client.xreadgroup(group_name, consumer_name, {stream_name: ">"}, count=count, block=block_ms)
            # res is list of (stream, [(id, {k: v}), ...])
            if not res:
                return []
            output = []
            for stream, entries in res:
                for eid, data in entries:
                    # data values were stored as json strings
                    decoded = {k: json.loads(v) for k, v in data.items()}
                    output.append({"id": eid, "data": decoded})
            return output
        except Exception as e:
            logger.error("Failed to xreadgroup from %s: %s", stream_name, e)
            return []

    def xack(self, stream_name: str, group_name: str, message_id: str) -> bool:
        """Acknowledge message processing in a consumer group."""
        try:
            self.redis_client.xack(stream_name, group_name, message_id)
            return True
        except Exception as e:
            logger.error("Failed to xack %s on %s/%s: %s", message_id, stream_name, group_name, e)
            return False

    def xpending(self, stream_name: str, group_name: str) -> Optional[Dict[str, Any]]:
        """Return pending messages info for a consumer group."""
        try:
            info = self.redis_client.xpending(stream_name, group_name)
            return info
        except Exception as e:
            logger.error("Failed to xpending on %s/%s: %s", stream_name, group_name, e)
            return None
    
    # Utility Methods
    def extend_session_ttl(self, session_id: str, ttl_seconds: int = 3600) -> bool:
        """Extend session TTL"""
        try:
            session_key = f"session:{session_id}"
            tree_key = f"tree_state:{session_id}"
            
            self.redis_client.expire(session_key, ttl_seconds)
            self.redis_client.expire(tree_key, ttl_seconds)
            return True
        except Exception as e:
            logger.error(f"Failed to extend session TTL: {e}")
            return False
    
    def get_session_ttl(self, session_id: str) -> int:
        """Get remaining TTL for session"""
        try:
            session_key = f"session:{session_id}"
            return self.redis_client.ttl(session_key)
        except Exception as e:
            logger.error(f"Failed to get session TTL: {e}")
            return -1
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            # This would need to be implemented based on your specific requirements
            # For now, return 0 as placeholder
            return 0
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0