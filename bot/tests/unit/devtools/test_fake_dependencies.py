"""Unit tests for deterministic fake dependency controls."""

from __future__ import annotations

import pytest
from ntheemba.devtools.fake_dependencies import (
    DEFAULT_FAKE_DEPENDENCIES,
    FakeDependencyController,
    FakeDependencyFailure,
)


@pytest.mark.asyncio
async def test_lists_stable_default_dependencies() -> None:
    controller = FakeDependencyController()

    behaviors = await controller.list_behaviors()

    assert tuple(item.dependency for item in behaviors) == DEFAULT_FAKE_DEPENDENCIES
    assert all(item.latency_ms == 0 for item in behaviors)
    assert all(item.fail_next == 0 for item in behaviors)
    assert all(not item.always_fail for item in behaviors)


@pytest.mark.asyncio
async def test_configures_and_reads_behavior() -> None:
    controller = FakeDependencyController()

    configured = await controller.configure(
        "tradeflow",
        latency_ms=250,
        fail_next=2,
        always_fail=False,
        failure_message="TradeFlow unavailable",
        operations=("create_order_request", "get_business_information"),
    )

    assert configured.latency_ms == 250
    assert configured.fail_next == 2
    assert configured.failure_message == "TradeFlow unavailable"
    assert configured.operations == ("create_order_request", "get_business_information")
    assert await controller.get_behavior("tradeflow") == configured


@pytest.mark.asyncio
async def test_fail_next_is_consumed_once() -> None:
    controller = FakeDependencyController()
    await controller.configure("publisher", fail_next=1)

    with pytest.raises(FakeDependencyFailure):
        await controller.before_call("publisher", "publish")

    await controller.before_call("publisher", "publish")
    assert (await controller.get_behavior("publisher")).fail_next == 0


@pytest.mark.asyncio
async def test_persistent_failure_is_not_consumed() -> None:
    controller = FakeDependencyController()
    await controller.configure("ncpc", always_fail=True, failure_message="NCPC offline")

    for _ in range(2):
        with pytest.raises(FakeDependencyFailure, match="NCPC offline"):
            await controller.before_call("ncpc", "search_products")

    assert (await controller.get_behavior("ncpc")).always_fail


@pytest.mark.asyncio
async def test_operation_filter_leaves_other_calls_untouched() -> None:
    controller = FakeDependencyController()
    await controller.configure(
        "tradeflow",
        fail_next=1,
        operations=("create_order_request",),
    )

    await controller.before_call("tradeflow", "get_business_information")
    assert (await controller.get_behavior("tradeflow")).fail_next == 1

    with pytest.raises(FakeDependencyFailure):
        await controller.before_call("tradeflow", "create_order_request")


@pytest.mark.asyncio
async def test_latency_uses_injected_sleeper() -> None:
    delays: list[float] = []

    async def sleeper(seconds: float) -> None:
        delays.append(seconds)

    controller = FakeDependencyController(sleeper=sleeper)
    await controller.configure("audit", latency_ms=125)

    await controller.before_call("audit", "record")

    assert delays == [0.125]


@pytest.mark.asyncio
async def test_run_wraps_async_operation() -> None:
    controller = FakeDependencyController()

    async def operation() -> str:
        return "completed"

    result = await controller.run("session_repository", "load", operation)

    assert result == "completed"


@pytest.mark.asyncio
async def test_reset_one_and_all() -> None:
    controller = FakeDependencyController()
    await controller.configure("audit", always_fail=True)
    await controller.configure("publisher", latency_ms=400)

    reset_audit = await controller.reset("audit")
    assert not reset_audit.always_fail
    assert (await controller.get_behavior("publisher")).latency_ms == 400

    reset = await controller.reset_all()
    assert all(item.latency_ms == 0 and not item.always_fail for item in reset)


@pytest.mark.asyncio
async def test_unknown_dependency_is_rejected() -> None:
    controller = FakeDependencyController()

    with pytest.raises(KeyError):
        await controller.get_behavior("missing")


@pytest.mark.asyncio
async def test_invalid_configuration_is_rejected() -> None:
    controller = FakeDependencyController()

    with pytest.raises(ValueError, match="latency_ms"):
        await controller.configure("audit", latency_ms=30_001)
    with pytest.raises(ValueError, match="failure_message"):
        await controller.configure("audit", failure_message=" ")


def test_custom_dependency_registry_requires_valid_names() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FakeDependencyController(())
    with pytest.raises(ValueError, match="invalid fake dependency"):
        FakeDependencyController(("not valid",))
