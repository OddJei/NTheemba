"""In-memory outgoing publisher."""

from __future__ import annotations

from ntheemba.ports.publisher import OutgoingMessage


class InMemoryOutgoingPublisher:
    """Capture messages in publication order."""

    def __init__(self) -> None:
        self.messages: list[OutgoingMessage] = []
        self.fail_next = False

    async def publish(self, message: OutgoingMessage) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("injected publisher failure")
        self.messages.append(message)

    async def publish_many(self, messages: tuple[OutgoingMessage, ...]) -> None:
        for message in messages:
            await self.publish(message)
