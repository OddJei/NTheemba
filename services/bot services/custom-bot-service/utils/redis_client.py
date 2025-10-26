"""Redis client placeholder for custom bot."""

class RedisClient:
    def __init__(self, url: str = "redis://localhost:6379/0"):
        self.url = url

    def get(self, key: str):
        return None

    def set(self, key: str, value, ex: int = None):
        return True
