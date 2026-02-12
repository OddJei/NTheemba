"""Async Redis queue worker that uses an executor for blocking operations.

Notes:
- We call blocking Redis operations (the existing `RedisClient.consume_from_queue`
  and `publish_to_queue`) using loop.run_in_executor so the asyncio loop isn't blocked.
- Handler execution (controller.process_message) is treated as blocking and also
  executed in the threadpool via run_in_executor.
- A semaphore limits concurrent handler executions to `max_workers`.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import uuid
from typing import Any, Dict, Optional

# Prometheus metrics (optional dependency)
try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
except Exception:
    PROMETHEUS_AVAILABLE = False

if PROMETHEUS_AVAILABLE:
    M_PROCESSED = Counter("bot_worker_processed_total", "Total processed messages")
    M_ERRORS = Counter("bot_worker_errors_total", "Total processing errors")
    M_RETRIES = Counter("bot_worker_retries_total", "Total processing retries")
    M_DLQ = Counter("bot_worker_dlq_total", "Total messages sent to DLQ")
    M_INFLIGHT = Gauge("bot_worker_inflight", "Number of inflight tasks")
    M_PROCESS_LATENCY = Histogram("bot_worker_process_latency_seconds", "Message processing latency seconds")

logger = logging.getLogger(__name__)


class RedisQueueWorker:
    def __init__(
        self,
        redis_client,
        controller,
        queue_name: str = "default_queue",
        dlq_name: Optional[str] = "default_queue_dlq",
        max_workers: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        poll_timeout: int = 1,
        backpressure_threshold: int = 1000,
        # Streams options
        use_streams: bool = False,
        stream_name: str = "default_stream",
        consumer_group: str = "default_group",
        consumer_name: str = "consumer_1",
        stream_block_ms: int = 1000,
        stream_read_count: int = 1,
    ):
        self.redis = redis_client
        self.controller = controller
        self.queue_name = queue_name
        self.dlq_name = dlq_name
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.poll_timeout = poll_timeout
        self.backpressure_threshold = backpressure_threshold
        # stream configuration
        self.use_streams = use_streams
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.stream_block_ms = stream_block_ms
        self.stream_read_count = stream_read_count

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._semaphore = asyncio.Semaphore(max_workers)
        self._main_task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._inflight_tasks = set()

        # metrics
        self.processed = 0
        self.errors = 0
        self.retries = 0
        self.dlq_count = 0

    async def start(self) -> None:
        logger.info("Starting Async RedisQueueWorker queue=%s workers=%d", self.queue_name, self.max_workers)
        self._stopping.clear()
        loop = asyncio.get_running_loop()
        # keep a handle to the main loop task
        # if using streams, ensure consumer group exists
        if self.use_streams:
            try:
                await loop.run_in_executor(None, lambda: self.redis.ensure_consumer_group(self.stream_name, self.consumer_group))
            except Exception:
                logger.exception("Failed to ensure consumer group for stream %s", self.stream_name)

        self._main_task = loop.create_task(self._run_loop())

    async def stop(self, timeout: float = 5.0) -> None:
        logger.info("Stopping Async RedisQueueWorker queue=%s", self.queue_name)
        self._stopping.set()
        if self._main_task:
            try:
                await asyncio.wait_for(self._main_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Main loop did not exit within timeout; cancelling")
                self._main_task.cancel()

        # wait for inflight tasks
        if self._inflight_tasks:
            logger.info("Waiting for %d inflight tasks to complete", len(self._inflight_tasks))
            await asyncio.gather(*self._inflight_tasks, return_exceptions=True)

        # shutdown executor
        self._executor.shutdown(wait=False)

    async def _run_loop(self) -> None:
        loop = asyncio.get_running_loop()
        backoff = 1.0
        while not self._stopping.is_set():
            try:
                # optional backpressure via LLEN
                try:
                    qlen = await loop.run_in_executor(None, lambda: self.redis.redis_client.llen(self.queue_name))
                    if qlen and qlen > self.backpressure_threshold:
                        logger.warning("Queue length %d exceeds backpressure_threshold %d: sleeping", qlen, self.backpressure_threshold)
                        await asyncio.sleep(min(1.0, qlen / float(self.backpressure_threshold)))
                except Exception:
                    pass
                if self.use_streams:
                    # read from stream consumer group
                    entries = await loop.run_in_executor(
                        None,
                        lambda: self.redis.xreadgroup(
                            self.stream_name,
                            self.consumer_group,
                            self.consumer_name,
                            block_ms=self.stream_block_ms,
                            count=self.stream_read_count,
                        ),
                    )

                    if not entries:
                        continue

                    for entry in entries:
                        msg_id = entry.get("id")
                        data = entry.get("data", {})
                        session_id = data.get("session_id") or data.get("session") or str(uuid.uuid4())
                        payload = data.get("payload") or {k: v for k, v in data.items() if k != "session_id"}

                        # schedule processing and ack on success
                        task = asyncio.create_task(self._process_and_ack(session_id, payload, msg_id))
                        self._inflight_tasks.add(task)
                        task.add_done_callback(lambda t: self._inflight_tasks.discard(t))

                else:
                    # blocking consume_from_queue in executor so it doesn't block the loop
                    raw_msg = await loop.run_in_executor(None, lambda: self.redis.consume_from_queue(self.queue_name, timeout=self.poll_timeout))
                    if not raw_msg:
                        continue

                    if not isinstance(raw_msg, dict):
                        logger.warning("Received non-dict message from queue: %r", raw_msg)
                        continue

                    session_id = raw_msg.get("session_id") or raw_msg.get("session") or str(uuid.uuid4())
                    payload = raw_msg.get("payload") or {k: v for k, v in raw_msg.items() if k != "session_id"}

                    # schedule processing
                    task = asyncio.create_task(self._process_message(session_id, payload))
                    self._inflight_tasks.add(task)
                    # cleanup when done
                    task.add_done_callback(lambda t: self._inflight_tasks.discard(t))

                backoff = 1.0

            except Exception as exc:
                logger.exception("Async RedisQueueWorker main loop error: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)

    async def _process_message(self, session_id: str, payload: Dict[str, Any]) -> None:
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            attempt = 0
            # track histogram timer if available via context manager
            timer_ctx = (M_PROCESS_LATENCY.time() if PROMETHEUS_AVAILABLE else None)
            if PROMETHEUS_AVAILABLE:
                M_INFLIGHT.inc()
            try:
                if timer_ctx:
                    # using context manager to measure duration
                    with timer_ctx:
                        while attempt <= self.max_retries and not self._stopping.is_set():
                            try:
                                attempt += 1
                                # run blocking handler in executor
                                result = await loop.run_in_executor(self._executor, lambda: self.controller.process_message(session_id, payload))
                                self.processed += 1
                                if PROMETHEUS_AVAILABLE:
                                    M_PROCESSED.inc()

                                # if result indicates success, optionally publish reply
                                try:
                                    if isinstance(result, dict) and result.get("success"):
                                        # publish processed payload/response to reply queue if configured
                                        try:
                                            reply_queue = getattr(self.redis, "reply_queue", None) or None
                                            if not reply_queue:
                                                reply_queue = getattr(self.redis, "reply_queue_name", None) or "reply_queue"
                                            await loop.run_in_executor(None, lambda: self.redis.publish_to_queue(reply_queue, {"session_id": session_id, "response": result}))
                                        except Exception:
                                            logger.exception("Failed to publish response to reply queue for session=%s", session_id)

                                except Exception:
                                    pass

                                if isinstance(result, dict) and result.get("success") is False:
                                    raise RuntimeError(f"Handler returned failure: {result}")
                                return

                            except Exception as exc:
                                self.errors += 1
                                if PROMETHEUS_AVAILABLE:
                                    M_ERRORS.inc()
                                if attempt <= self.max_retries:
                                    self.retries += 1
                                    if PROMETHEUS_AVAILABLE:
                                        M_RETRIES.inc()
                                    logger.warning(
                                        "Processing failed for session=%s attempt=%d/%d: %s. Retrying after %ss",
                                        session_id,
                                        attempt,
                                        self.max_retries,
                                        exc,
                                        self.retry_delay,
                                    )
                                    await asyncio.sleep(self.retry_delay * attempt)
                                    continue
                                else:
                                    logger.exception("Dropping message for session=%s after %d attempts: %s", session_id, attempt - 1, exc)
                                    try:
                                        await loop.run_in_executor(None, lambda: self.redis.publish_to_queue(self.dlq_name, {"session_id": session_id, "payload": payload, "error": str(exc)}))
                                        self.dlq_count += 1
                                        if PROMETHEUS_AVAILABLE:
                                            M_DLQ.inc()
                                    except Exception:
                                        logger.exception("Failed to publish to DLQ %s", self.dlq_name)
                                    return
                else:
                    # no histogram timer
                    while attempt <= self.max_retries and not self._stopping.is_set():
                        try:
                            attempt += 1
                            result = await loop.run_in_executor(self._executor, lambda: self.controller.process_message(session_id, payload))
                            self.processed += 1
                            if PROMETHEUS_AVAILABLE:
                                M_PROCESSED.inc()

                            if isinstance(result, dict) and result.get("success"):
                                try:
                                    reply_queue = getattr(self.redis, "reply_queue", None) or getattr(self.redis, "reply_queue_name", None) or "reply_queue"
                                    await loop.run_in_executor(None, lambda: self.redis.publish_to_queue(reply_queue, {"session_id": session_id, "response": result}))
                                except Exception:
                                    logger.exception("Failed to publish response to reply queue for session=%s", session_id)

                            if isinstance(result, dict) and result.get("success") is False:
                                raise RuntimeError(f"Handler returned failure: {result}")
                            return

                        except Exception as exc:
                            self.errors += 1
                            if PROMETHEUS_AVAILABLE:
                                M_ERRORS.inc()
                            if attempt <= self.max_retries:
                                self.retries += 1
                                if PROMETHEUS_AVAILABLE:
                                    M_RETRIES.inc()
                                logger.warning(
                                    "Processing failed for session=%s attempt=%d/%d: %s. Retrying after %ss",
                                    session_id,
                                    attempt,
                                    self.max_retries,
                                    exc,
                                    self.retry_delay,
                                )
                                await asyncio.sleep(self.retry_delay * attempt)
                                continue
                            else:
                                logger.exception("Dropping message for session=%s after %d attempts: %s", session_id, attempt - 1, exc)
                                try:
                                    await loop.run_in_executor(None, lambda: self.redis.publish_to_queue(self.dlq_name, {"session_id": session_id, "payload": payload, "error": str(exc)}))
                                    self.dlq_count += 1
                                    if PROMETHEUS_AVAILABLE:
                                        M_DLQ.inc()
                                except Exception:
                                    logger.exception("Failed to publish to DLQ %s", self.dlq_name)
                                return
            finally:
                if PROMETHEUS_AVAILABLE:
                    M_INFLIGHT.dec()

    async def _process_and_ack(self, session_id: str, payload: Dict[str, Any], message_id: str) -> None:
        """Process a stream message and XACK on success, or send to DLQ on failure."""
        loop = asyncio.get_running_loop()
        try:
            await self._process_message(session_id, payload)
            # ack the stream message
            try:
                await loop.run_in_executor(None, lambda: self.redis.xack(self.stream_name, self.consumer_group, message_id))
            except Exception:
                logger.exception("Failed to xack message %s in %s/%s", message_id, self.stream_name, self.consumer_group)
        except Exception:
            # processing error already handled in _process_message; optionally we could claim and move to DLQ
            try:
                await loop.run_in_executor(None, lambda: self.redis.publish_to_queue(self.dlq_name, {"session_id": session_id, "payload": payload, "error": "processing_failed"}))
                self.dlq_count += 1
            except Exception:
                logger.exception("Failed to publish to DLQ in _process_and_ack")


