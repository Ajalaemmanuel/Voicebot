"""Run every scenario in a batch, one call at a time (F9).

    python run_batch.py --scenarios scenarios/*.yaml --gap 30

Spawns a single agent worker for the whole batch (rather than one per call),
dispatches+dials each scenario in turn via call_runner.run_call, and keeps
going even if one call fails (N4) so a single bad scenario doesn't stop the
rest of the run. Prints a summary table at the end.
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import logging
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

import livekit.api as lkapi
from run import LiveKitApiCallClient, _ensure_agent_worker_running, run_one_call

load_dotenv()

logger = logging.getLogger("voicebot.run_batch")


@dataclass
class BatchEntry:
    scenario_path: str
    outcome: str
    duration_seconds: float
    error: str | None


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios",
        nargs="+",
        required=True,
        help="Scenario YAML paths or glob patterns, e.g. scenarios/*.yaml",
    )
    parser.add_argument("--gap", type=float, default=20.0, help="Seconds to wait between calls")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=float(os.environ.get("MAX_CALL_SECONDS", "240")),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    scenario_paths: list[str] = []
    for pattern in args.scenarios:
        matches = sorted(glob.glob(pattern))
        scenario_paths.extend(matches if matches else [pattern])

    if not scenario_paths:
        logger.error("No scenario files matched %s", args.scenarios)
        return 2

    for required in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "SIP_OUTBOUND_TRUNK_ID"):
        if not os.environ.get(required):
            logger.error("Missing required environment variable: %s (see .env.example)", required)
            return 2

    # One worker for the whole batch, not one per call (run_one_call never
    # spawns its own; only this top-level call does).
    worker_proc = _ensure_agent_worker_running()
    if worker_proc is not None:
        await asyncio.sleep(3.0)

    api = lkapi.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    client = LiveKitApiCallClient(api)

    results: list[BatchEntry] = []
    try:
        for i, scenario_path in enumerate(scenario_paths):
            logger.info("[%d/%d] Running %s", i + 1, len(scenario_paths), scenario_path)
            try:
                result = await run_one_call(scenario_path, args.max_seconds, client)
                results.append(
                    BatchEntry(scenario_path, result.outcome.value, result.duration_seconds, result.error)
                )
            except Exception as exc:  # noqa: BLE001 - one bad scenario must not kill the batch (N4)
                logger.exception("Unhandled error running %s", scenario_path)
                results.append(BatchEntry(scenario_path, "failed", 0.0, str(exc)))

            if i < len(scenario_paths) - 1:
                logger.info("Waiting %.0fs before the next call...", args.gap)
                await asyncio.sleep(args.gap)
    finally:
        await api.aclose()
        if worker_proc is not None:
            worker_proc.terminate()

    print("\n=== Batch summary ===")
    for entry in results:
        print(f"{entry.outcome:>10}  {entry.duration_seconds:6.1f}s  {entry.scenario_path}"
              + (f"  ({entry.error})" if entry.error else ""))

    failures = [e for e in results if e.outcome != "completed"]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
