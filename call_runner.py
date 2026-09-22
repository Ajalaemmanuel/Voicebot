"""Call orchestration control flow: create a room, dispatch our agent into
it, dial the test line via SIP, and wait for the call to finish or time out.

Async, and deliberately decoupled from the real LiveKit API client via a
small protocol, so this control flow is unit-testable without a network
connection (see docs/DECISIONS.md #10). `run.py` supplies the real async
LiveKit API client at runtime.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Protocol


class SipDialError(Exception):
    """Raised by a LiveKitCallClient when the outbound SIP dial fails
    (trunk auth rejected, invalid number, provider error, etc.)."""


class CallOutcome(str, Enum):
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    TIMEOUT = "timeout"
    FAILED = "failed"


@dataclass
class CallResult:
    outcome: CallOutcome
    room_name: str
    duration_seconds: float = 0.0
    error: str | None = None


class LiveKitCallClient(Protocol):
    async def create_room(self, name: str) -> None: ...

    async def dispatch_agent(self, room_name: str, scenario_path: str) -> None: ...

    async def wait_for_agent_ready(self, room_name: str, timeout: float) -> bool: ...

    async def create_sip_participant(
        self, room_name: str, phone_number: str, trunk_id: str
    ) -> None: ...

    async def is_sip_participant_active(self, room_name: str) -> bool: ...

    async def delete_room(self, room_name: str) -> None: ...


async def run_call(
    client: LiveKitCallClient,
    *,
    scenario_slug: str,
    room_name: str,
    scenario_path: str,
    phone_number: str,
    trunk_id: str,
    max_seconds: float,
    poll_interval: float = 1.0,
    answer_timeout: float | None = None,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    now_fn: Callable[[], float] = time.monotonic,
) -> CallResult:
    """Run one scenario's call end to end against `client` (F10, F11, N4)."""
    start = now_fn()
    await client.create_room(room_name)
    await client.dispatch_agent(room_name, scenario_path)

    agent_ready_timeout = min(15.0, max_seconds)
    if not await client.wait_for_agent_ready(room_name, agent_ready_timeout):
        await client.delete_room(room_name)
        return CallResult(
            outcome=CallOutcome.FAILED,
            room_name=room_name,
            duration_seconds=now_fn() - start,
            error="agent did not join the room before the readiness timeout",
        )

    try:
        await client.create_sip_participant(room_name, phone_number, trunk_id)
    except SipDialError as exc:
        await client.delete_room(room_name)
        return CallResult(
            outcome=CallOutcome.FAILED,
            room_name=room_name,
            duration_seconds=now_fn() - start,
            error=str(exc),
        )

    effective_answer_timeout = min(
        answer_timeout if answer_timeout is not None else max_seconds, max_seconds
    )
    answered = False
    while now_fn() - start < effective_answer_timeout:
        if await client.is_sip_participant_active(room_name):
            answered = True
            break
        await sleep_fn(poll_interval)

    if not answered:
        await client.delete_room(room_name)
        return CallResult(
            outcome=CallOutcome.NO_ANSWER,
            room_name=room_name,
            duration_seconds=now_fn() - start,
        )

    while now_fn() - start < max_seconds:
        if not await client.is_sip_participant_active(room_name):
            await client.delete_room(room_name)
            return CallResult(
                outcome=CallOutcome.COMPLETED,
                room_name=room_name,
                duration_seconds=now_fn() - start,
            )
        await sleep_fn(poll_interval)

    await client.delete_room(room_name)
    return CallResult(
        outcome=CallOutcome.TIMEOUT,
        room_name=room_name,
        duration_seconds=now_fn() - start,
    )
