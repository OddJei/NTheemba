"""Event emitter for custom bot."""


class EventEmitter:
    def __init__(self, base_url: str = "http://localhost:9000"):
        self.base_url = base_url

    def emit(self, event_type: str, payload: dict) -> bool:
        return True
