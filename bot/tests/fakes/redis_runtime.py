"""Small async Redis double for Phase 12 adapter tests."""

from __future__ import annotations

import json
from typing import Any


class WatchError(RuntimeError):
    pass


class FakeRedisPipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.watched: dict[str, int] = {}
        self.commands: list[tuple[str, bytes, int | None]] = []

    async def __aenter__(self) -> FakeRedisPipeline:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def watch(self, key: str) -> None:
        self.watched[key] = self.redis.versions.get(key, 0)

    async def get(self, key: str) -> bytes | None:
        return await self.redis.get(key)

    def multi(self) -> None:
        return None

    def set(self, key: str, value: bytes, *, ex: int | None = None) -> None:
        self.commands.append((key, value, ex))

    async def execute(self) -> list[bool]:
        for key, version in self.watched.items():
            if self.redis.versions.get(key, 0) != version:
                raise WatchError("watched key changed")
        results: list[bool] = []
        for key, value, ex in self.commands:
            results.append(bool(await self.redis.set(key, value, ex=ex)))
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.versions: dict[str, int] = {}
        self.expiries: dict[str, int] = {}
        self.streams: dict[str, list[tuple[str, dict[str, bytes]]]] = {}
        self.stream_counters: dict[str, int] = {}
        self.group_offsets: dict[tuple[str, str], int] = {}
        self.pending: dict[tuple[str, str, str], str] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def set(
        self,
        key: str,
        value: bytes | str,
        *,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        if nx and key in self.values:
            return None
        payload = value.encode() if isinstance(value, str) else value
        self.values[key] = payload
        self.versions[key] = self.versions.get(key, 0) + 1
        if ex is not None:
            self.expiries[key] = ex
        if px is not None:
            self.expiries[key] = max(1, px // 1000)
        return True

    async def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.versions[key] = self.versions.get(key, 0) + 1
        return int(existed)

    def pipeline(self, *, transaction: bool = True) -> FakeRedisPipeline:
        assert transaction is True
        return FakeRedisPipeline(self)

    async def eval(self, script: str, _key_count: int, key: str, *args: Any) -> int:
        current = self.values.get(key)
        if "cjson.decode" in script:
            if current is None:
                return 0
            decoded = json.loads(current.decode())
            owner = str(args[0])
            if decoded.get("owner_token") != owner:
                return 0
            if "status ~= 'pending'" in script:
                if decoded.get("status") != "pending":
                    return 0
                return await self.delete(key)
            payload = args[1]
            ttl = int(args[2])
            await self.set(key, payload, ex=ttl)
            return 1

        owner = str(args[0]).encode()
        if current != owner:
            return 0
        if "pexpire" in script:
            self.expiries[key] = max(1, int(args[1]) // 1000)
            return 1
        return await self.delete(key)

    async def xgroup_create(
        self,
        stream: str,
        group: str,
        *,
        id: str = "0",
        mkstream: bool = False,
    ) -> bool:
        key = (stream, group)
        if key in self.group_offsets:
            raise RuntimeError("BUSYGROUP Consumer Group name already exists")
        if mkstream:
            self.streams.setdefault(stream, [])
        self.group_offsets[key] = 0
        return True

    async def xadd(
        self,
        stream: str,
        fields: dict[str, Any],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        del approximate
        counter = self.stream_counters.get(stream, 0) + 1
        self.stream_counters[stream] = counter
        entry_id = f"{counter}-0"
        encoded = {
            str(key): value if isinstance(value, bytes) else str(value).encode()
            for key, value in fields.items()
        }
        entries = self.streams.setdefault(stream, [])
        entries.append((entry_id, encoded))
        if maxlen is not None and len(entries) > maxlen:
            del entries[: len(entries) - maxlen]
        return entry_id

    async def xreadgroup(
        self,
        group: str,
        consumer: str,
        *,
        streams: dict[str, str],
        count: int = 1,
        block: int | None = None,
    ) -> list[tuple[str, list[tuple[str, dict[str, bytes]]]]]:
        del block
        stream, marker = next(iter(streams.items()))
        assert marker == ">"
        key = (stream, group)
        offset = self.group_offsets.get(key, 0)
        entries = self.streams.get(stream, [])[offset : offset + count]
        if not entries:
            return []
        self.group_offsets[key] = offset + len(entries)
        for entry_id, _fields in entries:
            self.pending[(stream, group, entry_id)] = consumer
        return [(stream, entries)]

    async def xautoclaim(
        self,
        stream: str,
        group: str,
        consumer: str,
        *,
        min_idle_time: int,
        start_id: str = "0-0",
        count: int = 1,
    ) -> tuple[str, list[tuple[str, dict[str, bytes]]], list[str]]:
        del min_idle_time, start_id
        claimed: list[tuple[str, dict[str, bytes]]] = []
        entries_by_id = dict(self.streams.get(stream, []))
        for key, owner in list(self.pending.items()):
            pending_stream, pending_group, entry_id = key
            if pending_stream != stream or pending_group != group or owner == consumer:
                continue
            fields = entries_by_id.get(entry_id)
            if fields is None:
                continue
            self.pending[key] = consumer
            claimed.append((entry_id, fields))
            if len(claimed) >= count:
                break
        return "0-0", claimed, []

    async def xack(self, stream: str, group: str, *entry_ids: str) -> int:
        removed = 0
        for entry_id in entry_ids:
            if self.pending.pop((stream, group, entry_id), None) is not None:
                removed += 1
        return removed

    async def xrange(
        self,
        stream: str,
        *,
        min: str,
        max: str,
        count: int | None = None,
    ) -> list[tuple[str, dict[str, bytes]]]:
        values = [entry for entry in self.streams.get(stream, []) if min <= entry[0] <= max]
        return values if count is None else values[:count]
