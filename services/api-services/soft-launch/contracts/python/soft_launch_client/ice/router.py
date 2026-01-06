from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict


Handler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class PluginRegistration:
    name: str
    handler: Handler


class IceRouter:
    """Minimal ICE router.

    - Bot (or API) calls ICE with a `plugin` name and payload.
    - ICE looks up the automation plugin handler.

    This keeps the bot contract stable: 1 call = 1 automation step.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Handler] = {}

    def register(self, name: str, handler: Handler) -> None:
        if name in self._registry:
            raise KeyError(f"Plugin already registered: {name}")
        self._registry[name] = handler

    async def handle(self, *, plugin: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if plugin not in self._registry:
            return {"error": "unknown_plugin", "message": f"Unknown plugin: {plugin}"}
        return await self._registry[plugin](payload)
