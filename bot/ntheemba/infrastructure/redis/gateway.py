"""Redis Streams implementation of the acknowledged gateway queue."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ntheemba.domain.business import ChannelRole, ChannelScope
from ntheemba.domain.gateway import InboundGatewayMessage, OutboundGatewayMessage
from ntheemba.infrastructure.redis.keys import RedisKeyspace
from ntheemba.ports.gateway import ClaimedInboundMessage, ClaimedOutboundMessage


class RedisReliableGatewayQueue:
    """Durable gateway delivery using consumer groups and explicit acknowledgement."""

    def __init__(
        self,
        client: Any,
        keyspace: RedisKeyspace,
        *,
        group_name: str = "ntheemba",
        stream_max_length: int = 100_000,
        claim_idle_seconds: int = 60,
    ) -> None:
        if not group_name.strip():
            raise ValueError("group_name must not be empty")
        if stream_max_length < 100:
            raise ValueError("stream_max_length must be at least 100")
        if claim_idle_seconds < 1:
            raise ValueError("claim_idle_seconds must be greater than zero")
        self.client = client
        self.keyspace = keyspace
        self.group_name = group_name
        self.stream_max_length = stream_max_length
        self.claim_idle_seconds = claim_idle_seconds
        self._groups_ready = False

    async def initialize(self) -> None:
        if self._groups_ready:
            return
        for stream in (
            self.keyspace.gateway_inbound_stream(),
            self.keyspace.gateway_outbound_stream(),
        ):
            try:
                await self.client.xgroup_create(
                    stream,
                    self.group_name,
                    id="0",
                    mkstream=True,
                )
            except Exception as error:
                if "BUSYGROUP" not in str(error):
                    raise
        self._groups_ready = True

    async def enqueue_inbound(self, message: InboundGatewayMessage) -> str:
        await self.initialize()
        return self._decode_id(
            await self.client.xadd(
                self.keyspace.gateway_inbound_stream(),
                {"payload": self._encode_inbound(message), "attempt": "0"},
                maxlen=self.stream_max_length,
                approximate=True,
            )
        )

    async def claim_inbound(self, consumer_id: str) -> ClaimedInboundMessage | None:
        self._validate_consumer(consumer_id)
        await self.initialize()
        entry = await self._claim(self.keyspace.gateway_inbound_stream(), consumer_id)
        if entry is None:
            return None
        delivery_id, fields = entry
        attempt = int(self._field(fields, "attempt", "0")) + 1
        return ClaimedInboundMessage(
            delivery_id,
            consumer_id,
            self._decode_inbound(self._field(fields, "payload")),
            attempt,
        )

    async def acknowledge_inbound(self, delivery_id: str, consumer_id: str) -> None:
        self._validate_owner(delivery_id, consumer_id)
        await self.client.xack(
            self.keyspace.gateway_inbound_stream(), self.group_name, delivery_id
        )

    async def retry_inbound(self, delivery_id: str, consumer_id: str) -> None:
        self._validate_owner(delivery_id, consumer_id)
        stream = self.keyspace.gateway_inbound_stream()
        fields = await self._entry_fields(stream, delivery_id)
        attempt = int(self._field(fields, "attempt", "0")) + 1
        await self.client.xadd(
            stream,
            {"payload": self._field(fields, "payload"), "attempt": str(attempt)},
            maxlen=self.stream_max_length,
            approximate=True,
        )
        await self.client.xack(stream, self.group_name, delivery_id)

    async def dead_letter_inbound(
        self,
        delivery_id: str,
        consumer_id: str,
        reason: str,
    ) -> None:
        self._validate_owner(delivery_id, consumer_id)
        if not reason.strip():
            raise ValueError("reason must not be empty")
        stream = self.keyspace.gateway_inbound_stream()
        fields = await self._entry_fields(stream, delivery_id)
        await self.client.xadd(
            self.keyspace.gateway_inbound_dead_letter_stream(),
            {
                "payload": self._field(fields, "payload"),
                "attempt": self._field(fields, "attempt", "0"),
                "reason": reason,
                "failed_at": datetime.now(UTC).isoformat(),
                "source_delivery_id": delivery_id,
            },
            maxlen=self.stream_max_length,
            approximate=True,
        )
        await self.client.xack(stream, self.group_name, delivery_id)

    async def enqueue_outbound(self, message: OutboundGatewayMessage) -> str:
        await self.initialize()
        stream = self.keyspace.gateway_outbound_stream(message.gateway_id)
        await self._ensure_group(stream)
        return self._decode_id(
            await self.client.xadd(
                stream,
                {"payload": self._encode_outbound(message), "attempt": "0"},
                maxlen=self.stream_max_length,
                approximate=True,
            )
        )

    async def claim_outbound(
        self, consumer_id: str, gateway_id: str = ""
    ) -> ClaimedOutboundMessage | None:
        self._validate_consumer(consumer_id)
        await self.initialize()
        entry = await self._claim(self.keyspace.gateway_outbound_stream(gateway_id), consumer_id)
        if entry is None:
            return None
        delivery_id, fields = entry
        attempt = int(self._field(fields, "attempt", "0")) + 1
        return ClaimedOutboundMessage(
            delivery_id,
            consumer_id,
            self._decode_outbound(self._field(fields, "payload")),
            attempt,
        )

    async def acknowledge_outbound(
        self, delivery_id: str, consumer_id: str, gateway_id: str = ""
    ) -> None:
        self._validate_owner(delivery_id, consumer_id)
        acknowledged = await self.client.xack(
            self.keyspace.gateway_outbound_stream(gateway_id), self.group_name, delivery_id
        )
        if int(acknowledged or 0) != 1:
            raise PermissionError("outbound delivery belongs to another gateway or consumer")

    async def retry_outbound(
        self, delivery_id: str, consumer_id: str, gateway_id: str = ""
    ) -> None:
        self._validate_owner(delivery_id, consumer_id)
        stream = self.keyspace.gateway_outbound_stream(gateway_id)
        fields = await self._entry_fields(stream, delivery_id)
        attempt = int(self._field(fields, "attempt", "0")) + 1
        await self.client.xadd(
            stream,
            {"payload": self._field(fields, "payload"), "attempt": str(attempt)},
            maxlen=self.stream_max_length,
            approximate=True,
        )
        await self.client.xack(stream, self.group_name, delivery_id)

    async def dead_letter_outbound(
        self,
        delivery_id: str,
        consumer_id: str,
        reason: str,
        gateway_id: str = "",
    ) -> None:
        self._validate_owner(delivery_id, consumer_id)
        if not reason.strip():
            raise ValueError("reason must not be empty")
        stream = self.keyspace.gateway_outbound_stream(gateway_id)
        fields = await self._entry_fields(stream, delivery_id)
        await self.client.xadd(
            self.keyspace.gateway_outbound_dead_letter_stream(),
            {
                "payload": self._field(fields, "payload"),
                "attempt": self._field(fields, "attempt", "0"),
                "reason": reason,
                "failed_at": datetime.now(UTC).isoformat(),
                "source_delivery_id": delivery_id,
            },
            maxlen=self.stream_max_length,
            approximate=True,
        )
        await self.client.xack(stream, self.group_name, delivery_id)

    async def _claim(self, stream: str, consumer_id: str) -> tuple[str, Any] | None:
        await self._ensure_group(stream)
        stale = await self._claim_stale(stream, consumer_id)
        if stale is not None:
            return stale
        return await self._claim_new(stream, consumer_id)

    async def _ensure_group(self, stream: str) -> None:
        try:
            await self.client.xgroup_create(stream, self.group_name, id="0", mkstream=True)
        except Exception as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def _claim_stale(
        self,
        stream: str,
        consumer_id: str,
    ) -> tuple[str, Any] | None:
        xautoclaim = getattr(self.client, "xautoclaim", None)
        if xautoclaim is None:
            return None
        result = await xautoclaim(
            stream,
            self.group_name,
            consumer_id,
            min_idle_time=self.claim_idle_seconds * 1000,
            start_id="0-0",
            count=1,
        )
        if not result or len(result) < 2:
            return None
        entries = result[1]
        if not entries:
            return None
        delivery_id, fields = entries[0]
        return self._decode_id(delivery_id), fields

    async def _claim_new(self, stream: str, consumer_id: str) -> tuple[str, Any] | None:
        result = await self.client.xreadgroup(
            self.group_name,
            consumer_id,
            streams={stream: ">"},
            count=1,
            block=1,
        )
        if not result:
            return None
        _stream_name, entries = result[0]
        if not entries:
            return None
        delivery_id, fields = entries[0]
        return self._decode_id(delivery_id), fields

    async def _entry_fields(self, stream: str, delivery_id: str) -> Any:
        entries = await self.client.xrange(stream, min=delivery_id, max=delivery_id, count=1)
        if not entries:
            raise LookupError(delivery_id)
        return entries[0][1]

    @staticmethod
    def _encode_inbound(message: InboundGatewayMessage) -> str:
        return json.dumps(
            {
                "request_id": message.request_id,
                "message_id": message.message_id,
                "channel_instance_id": message.channel_instance_id,
                "provider": message.provider,
                "recipient_phone": message.recipient_phone,
                "customer_phone": message.customer_phone,
                "text": message.text,
                "received_at": message.received_at.isoformat(),
                "schema_version": message.schema_version,
                "metadata": dict(message.metadata),
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _decode_inbound(payload: str) -> InboundGatewayMessage:
        data = json.loads(payload)
        return InboundGatewayMessage(
            request_id=str(data["request_id"]),
            message_id=str(data["message_id"]),
            channel_instance_id=str(data["channel_instance_id"]),
            provider=str(data["provider"]),
            recipient_phone=str(data["recipient_phone"]),
            customer_phone=str(data["customer_phone"]),
            text=str(data["text"]),
            received_at=datetime.fromisoformat(str(data["received_at"])),
            schema_version=str(data["schema_version"]),
            metadata=dict(data.get("metadata", {})),
        )

    @staticmethod
    def _encode_outbound(message: OutboundGatewayMessage) -> str:
        return json.dumps(
            {
                "reply_id": message.reply_id,
                "request_id": message.request_id,
                "business_id": message.business_id,
                "channel_instance_id": message.channel_instance_id,
                "recipient_phone": message.recipient_phone,
                "text": message.text,
                "gateway_id": message.gateway_id,
                "delivery_target": message.delivery_target,
                "schema_version": message.schema_version,
                "metadata": dict(message.metadata),
                "scope": message.scope.value,
                "platform_role": message.platform_role.value if message.platform_role else "",
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _decode_outbound(payload: str) -> OutboundGatewayMessage:
        data = json.loads(payload)
        return OutboundGatewayMessage(
            reply_id=str(data["reply_id"]),
            request_id=str(data["request_id"]),
            business_id=str(data["business_id"]),
            channel_instance_id=str(data["channel_instance_id"]),
            recipient_phone=str(data["recipient_phone"]),
            text=str(data["text"]),
            gateway_id=str(data.get("gateway_id", "")),
            delivery_target=str(data.get("delivery_target", "")),
            schema_version=str(data["schema_version"]),
            metadata=dict(data.get("metadata", {})),
            scope=ChannelScope(str(data.get("scope", ChannelScope.BUSINESS.value))),
            platform_role=(
                ChannelRole(str(data["platform_role"]))
                if str(data.get("platform_role", "")).strip()
                else None
            ),
        )

    @staticmethod
    def _field(fields: Any, name: str, default: str | None = None) -> str:
        value = fields.get(name)
        if value is None:
            value = fields.get(name.encode())
        if value is None:
            if default is None:
                raise ValueError(f"stream field {name!r} is missing")
            return default
        return value.decode() if isinstance(value, bytes) else str(value)

    @staticmethod
    def _decode_id(value: Any) -> str:
        return value.decode() if isinstance(value, bytes) else str(value)

    @staticmethod
    def _validate_consumer(consumer_id: str) -> None:
        if not consumer_id.strip():
            raise ValueError("consumer_id must not be empty")

    @staticmethod
    def _validate_owner(delivery_id: str, consumer_id: str) -> None:
        if not delivery_id.strip() or not consumer_id.strip():
            raise ValueError("delivery_id and consumer_id must not be empty")
