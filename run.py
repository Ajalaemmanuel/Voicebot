"""Single-command runner for one scenario call (F8).

    python run.py --scenario scenarios/simple_scheduling_1.yaml

Ensures the agent worker is running, creates a room, explicitly dispatches
our agent into it (agent.py's entrypoint then builds the AgentSession), dials
the fixed test line via LiveKit's SIP API once the agent has joined, and
waits for the call to finish or hit the configured timeout. See
docs/TECHNICAL_DESIGN.md "run.py lifecycle" for the full flow and
docs/DECISIONS.md #6 for why LiveKit Cloud + a SIP trunk provider (e.g.
Twilio) is used for telephony.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

import livekit.api as lkapi
from call_runner import CallOutcome, LiveKitCallClient, SipDialError, run_call
from scenario_loader import load_scenario

load_dotenv()

logger = logging.getLogger("voicebot.run")

AGENT_NAME = "patient-tester"
SIP_PARTICIPANT_IDENTITY = "test-line"
CALLS_DIR = Path(__file__).parent / "calls"


class LiveKitApiCallClient(LiveKitCallClient):
    """Adapts the real (async) LiveKit API to the small protocol
    call_runner.run_call depends on, so run_call itself stays unit-testable
    without a network connection."""

    def __init__(self, api: lkapi.LiveKitAPI, agent_name: str = AGENT_NAME):
        self._api = api
        self._agent_name = agent_name

    async def create_room(self, name: str) -> None:
        await self._api.room.create_room(lkapi.CreateRoomRequest(name=name))

    async def dispatch_agent(self, room_name: str, scenario_path: str) -> None:
        # room_name doubles as the call_id / calls/<call_id> folder name, so
        # the orchestrator-side outcome (run_result.json, written below in
        # run_one_call) and the agent-side artifacts (transcript/audio/
        # metadata.json, written by agent.py) always land in the same place.
        metadata = json.dumps({"scenario_path": scenario_path, "call_id": room_name})
        await self._api.agent_dispatch.create_dispatch(
            lkapi.CreateAgentDispatchRequest(
                room=room_name, agent_name=self._agent_name, metadata=metadata
            )
        )

    async def wait_for_agent_ready(self, room_name: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            participants = await self._list_participants(room_name)
            if any(p.identity != SIP_PARTICIPANT_IDENTITY for p in participants):
                return True
            await asyncio.sleep(1.0)
        return False

    async def create_sip_participant(
        self, room_name: str, phone_number: str, trunk_id: str
    ) -> None:
        try:
            await self._api.sip.create_sip_participant(
                lkapi.CreateSIPParticipantRequest(
                    room_name=room_name,
                    sip_trunk_id=trunk_id,
                    sip_call_to=phone_number,
                    participant_identity=SIP_PARTICIPANT_IDENTITY,
                )
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a typed failure (F11)
            raise SipDialError(str(exc)) from exc

    async def is_sip_participant_active(self, room_name: str) -> bool:
        participants = await self._list_participants(room_name)
        return any(p.identity == SIP_PARTICIPANT_IDENTITY for p in participants)

    async def delete_room(self, room_name: str) -> None:
        try:
            await self._api.room.delete_room(lkapi.DeleteRoomRequest(room=room_name))
        except Exception:
            logger.debug("delete_room(%s) failed (already gone?)", room_name, exc_info=True)

    async def _list_participants(self, room_name: str):
        response = await self._api.room.list_participants(
            lkapi.ListParticipantsRequest(room=room_name)
        )
        return response.participants


def _ensure_agent_worker_running() -> subprocess.Popen | None:
    """Spawn `python agent.py start` if a worker doesn't already seem to be
    running, so a single `python run.py ...` invocation is enough (F8)."""
    # A simple heuristic: if the caller already has a worker running (e.g.
    # `python agent.py dev` in another terminal for local iteration), don't
    # spawn a second one. Controlled via an env var so run_batch.py's loop
    # doesn't spawn a fresh worker per scenario.
    if os.environ.get("VOICEBOT_SKIP_WORKER_SPAWN") == "1":
        return None

    logger.info("Starting agent worker subprocess (python agent.py start)...")
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "agent.py"), "start"],
        stdout=None,
        stderr=None,
    )
    return proc


async def run_one_call(scenario_path: str, max_seconds: float, agent_client: LiveKitApiCallClient):
    scenario = load_scenario(scenario_path)
    room_name = f"{scenario.slug}-{uuid.uuid4().hex[:8]}"
    phone_number = os.environ.get("TEST_LINE_NUMBER", "+18054398008")
    trunk_id = os.environ["SIP_OUTBOUND_TRUNK_ID"]

    logger.info("Calling %s for scenario '%s' (room=%s)", phone_number, scenario.slug, room_name)

    result = await run_call(
        agent_client,
        scenario_slug=scenario.slug,
        room_name=room_name,
        scenario_path=str(scenario.source_path),
        phone_number=phone_number,
        trunk_id=trunk_id,
        max_seconds=max_seconds,
    )

    call_dir = CALLS_DIR / room_name
    call_dir.mkdir(parents=True, exist_ok=True)
    (call_dir / "run_result.json").write_text(
        json.dumps(
            {
                "room_name": room_name,
                "scenario_slug": scenario.slug,
                "outcome": result.outcome.value,
                "duration_seconds": result.duration_seconds,
                "error": result.error,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if result.outcome == CallOutcome.COMPLETED:
        logger.info("Call completed (%.0fs). Artifacts are under calls/%s/", result.duration_seconds, room_name)
    else:
        logger.error(
            "Call did not complete normally: outcome=%s error=%s",
            result.outcome.value,
            result.error,
        )
    return result


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, help="Path to a scenario YAML file")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=float(os.environ.get("MAX_CALL_SECONDS", "240")),
        help="Hard ceiling on call duration (F10)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    for required in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "SIP_OUTBOUND_TRUNK_ID"):
        if not os.environ.get(required):
            logger.error("Missing required environment variable: %s (see .env.example)", required)
            return 2

    worker_proc = _ensure_agent_worker_running()
    if worker_proc is not None:
        # Give the worker a moment to register with LiveKit Cloud before we dispatch.
        await asyncio.sleep(3.0)

    api = lkapi.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    client = LiveKitApiCallClient(api)

    try:
        result = await run_one_call(args.scenario, args.max_seconds, client)
    finally:
        await api.aclose()
        if worker_proc is not None:
            worker_proc.terminate()

    return 0 if result.outcome == CallOutcome.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
