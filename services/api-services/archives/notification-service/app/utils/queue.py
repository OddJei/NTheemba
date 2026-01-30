"""Simple in-memory queue placeholder for retries / dev.

Replace with a Redis-backed queue in production.
"""
from collections import deque
from threading import Lock


class InMemoryQueue:
    def __init__(self):
        self._q = deque()
        self._lock = Lock()

    def push(self, item):
        with self._lock:
            self._q.append(item)

    def pop(self):
        with self._lock:
            return self._q.popleft() if self._q else None


default_queue = InMemoryQueue()
