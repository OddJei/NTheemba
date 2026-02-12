"""
Phase 6: Load Testing Suite

Comprehensive load tests for ICE service endpoints.
Tests reserve, confirm, payment_status, and concurrent operations.

Run with: locust -f load_tests.py --headless -u 100 -r 10 -t 5m
"""

from __future__ import annotations

import random
import uuid
from typing import Any

from locust import HttpUser, task, between, events


# Test data generators
def gen_event_id() -> str:
    """Generate unique event ID."""
    return f"evt_{uuid.uuid4().hex[:12]}"


def gen_session_id() -> str:
    """Generate session ID."""
    return f"sess_{uuid.uuid4().hex[:12]}"


def gen_order_id() -> str:
    """Generate order ID."""
    return f"ord_{uuid.uuid4().hex[:12]}"


def gen_phone() -> str:
    """Generate test phone number."""
    return f"26097{random.randint(0000000, 9999999):07d}"


class ICEServiceUser(HttpUser):
    """Simulated user performing ICE service operations."""

    wait_time = between(0.5, 2.0)  # 0.5-2s between operations

    def on_start(self) -> None:
        """Initialize user session."""
        self.event_id = gen_event_id()
        self.session_id = gen_session_id()
        self.order_id = gen_order_id()
        self.phone = gen_phone()

    @task(5)
    def hydrate_session(self) -> None:
        """Load test POST /api/v1/hydrate/session."""
        payload = {
            "event_id": gen_event_id(),
            "session_id": gen_session_id(),
            "user_id": f"user_{uuid.uuid4().hex[:8]}",
            "bot_id": f"bot_{random.randint(1, 10)}",
            "required_blobs": ["session", "order_draft", "bot_meta"],
        }

        with self.client.post(
            "/api/v1/hydrate/session",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}: {response.text}")

    @task(3)
    def reserve_items(self) -> None:
        """Load test POST /api/v1/reserve."""
        payload = {
            "event_id": gen_event_id(),
            "session_id": gen_session_id(),
            "user_id": f"user_{uuid.uuid4().hex[:8]}",
            "business_id": f"biz_{random.randint(1, 5)}",
            "cart_id": f"cart_{uuid.uuid4().hex[:8]}",
            "payment_method": random.choice(["mobile_money", "card", "cash"]),
            "payment_number": gen_phone(),
            "idempotency_key": gen_event_id(),
        }

        with self.client.post(
            "/api/v1/reserve",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                # Extract order_draft_id for confirm flow
                try:
                    data = response.json()
                    self.order_id = data.get("order_draft_id")
                except Exception:
                    pass
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def confirm_order(self) -> None:
        """Load test POST /api/v1/confirm."""
        payload = {
            "event_id": gen_event_id(),
            "order_draft_id": self.order_id,
            "user_id": f"user_{uuid.uuid4().hex[:8]}",
            "payment_details": {
                "payment_method": "mobile_money",
                "phone_number": gen_phone(),
                "amount_minor": random.randint(10000, 500000),
            },
            "delivery_details": {
                "method": random.choice(["pickup", "delivery"]),
                "address": "Test Address",
            },
            "idempotency_key": gen_event_id(),
        }

        with self.client.post(
            "/api/v1/confirm",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    data = response.json()
                    self.order_id = data.get("order_id")
                except Exception:
                    pass
            else:
                response.failure(f"Status {response.status_code}")

    @task(4)
    def check_payment_status(self) -> None:
        """Load test GET /api/v1/orders/{order_id}/payment_status."""
        with self.client.get(
            f"/api/v1/orders/{self.order_id}/payment_status",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def cancel_order(self) -> None:
        """Load test POST /api/v1/orders/{order_id}/cancel."""
        payload = {
            "reason": random.choice(["USER_CANCELLED", "PAYMENT_FAILED", "OUT_OF_STOCK"]),
        }

        with self.client.post(
            f"/api/v1/orders/{self.order_id}/cancel",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def health_check(self) -> None:
        """Load test GET /health."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")


class ConcurrentReserveUser(HttpUser):
    """Specialized user for concurrent reserve/confirm stress test."""

    wait_time = between(0, 0.5)  # Very fast requests

    def on_start(self) -> None:
        """Initialize."""
        self.session_id = gen_session_id()

    @task
    def concurrent_reserve(self) -> None:
        """Simulate many rapid reserve requests."""
        payload = {
            "event_id": gen_event_id(),
            "session_id": self.session_id,
            "user_id": f"user_{uuid.uuid4().hex[:8]}",
            "business_id": f"biz_{random.randint(1, 5)}",
            "cart_id": f"cart_{uuid.uuid4().hex[:8]}",
            "payment_method": "mobile_money",
            "payment_number": gen_phone(),
            "idempotency_key": gen_event_id(),
        }

        with self.client.post(
            "/api/v1/reserve",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")


class IdempotencyTestUser(HttpUser):
    """Test idempotency: same request twice should return same result."""

    wait_time = between(2, 4)

    @task
    def idempotent_reserve(self) -> None:
        """Send same reserve request twice."""
        idempotency_key = gen_event_id()

        # First request
        payload = {
            "event_id": gen_event_id(),
            "session_id": gen_session_id(),
            "user_id": f"user_{uuid.uuid4().hex[:8]}",
            "business_id": f"biz_{random.randint(1, 5)}",
            "cart_id": f"cart_{uuid.uuid4().hex[:8]}",
            "payment_method": "mobile_money",
            "payment_number": gen_phone(),
            "idempotency_key": idempotency_key,
        }

        with self.client.post("/api/v1/reserve", json=payload) as response1:
            if response1.status_code != 200:
                return

            result1 = response1.json()

            # Second request with same idempotency key
            with self.client.post("/api/v1/reserve", json=payload) as response2:
                result2 = response2.json()

                # Results should be identical
                if result1 == result2:
                    self.client.last_response.success()
                else:
                    self.client.last_response.failure("Idempotency check failed")


# ============================================================================
# Event Handlers for Reporting
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print("\n" + "=" * 60)
    print("ICE SERVICE LOAD TEST STARTED")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("\n" + "=" * 60)
    print("ICE SERVICE LOAD TEST COMPLETED")
    print("=" * 60)
    
    # Print summary
    stats = environment.stats
    print("\n--- Request Statistics ---")
    for method, path in stats.entries.keys():
        entry = stats.entries[(method, path)]
        print(f"\n{method} {path}:")
        print(f"  Total: {entry.num_requests}")
        print(f"  Failed: {entry.num_failures}")
        print(f"  Avg latency: {entry.avg_response_time:.2f}ms")
        print(f"  P95: {entry.get_response_time_percentile(0.95):.2f}ms")
        print(f"  P99: {entry.get_response_time_percentile(0.99):.2f}ms")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Called for each request."""
    if exception:
        print(f"REQUEST FAILED: {request_type} {name} - {exception}")


# ============================================================================
# Test Scenarios
# ============================================================================

"""
Run different test scenarios:

1. Standard load test (balanced workload):
   locust -f load_tests.py --headless -u 100 -r 10 -t 5m

2. Stress test (max throughput):
   locust -f load_tests.py --headless -u 500 -r 50 -t 10m

3. Concurrent reserve/confirm:
   locust -f load_tests.py::ConcurrentReserveUser --headless -u 200 -r 20 -t 5m

4. Idempotency test:
   locust -f load_tests.py::IdempotencyTestUser --headless -u 50 -r 5 -t 10m

Expected Results:
- P95 latency: <500ms
- P99 latency: <1000ms
- Error rate: <1%
- Throughput: >1000 req/s (depends on server)
"""
