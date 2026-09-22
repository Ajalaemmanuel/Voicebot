"""LiveKit Agents worker: the "patient" caller persona.

Built in pipeline mode (separate STT / LLM / TTS / VAD / turn-detector
components — no realtime/speech-to-speech model, per the assignment's
constraint and docs/DECISIONS.md #1). Dispatched into a room by run.py /
run_batch.py with a scenario file path as job metadata; on start it dials
the fixed test line via SIP, then drives the conversation, recording audio
and a transcript to calls/<run>/.

See docs/TECHNICAL_DESIGN.md for the full per-turn data flow.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
    inference,
    llm,
)
from livekit.plugins import cartesia, deepgram, openai, silero

from rag import PatientHistoryIndex
from recorder import DualTrackRecorder, convert_to_compressed
from scenario_loader import Scenario, load_scenario
from transcript import TranscriptWriter

load_dotenv()

logger = logging.getLogger("voicebot.agent")

SAMPLE_RATE = 16000
CALLS_DIR = Path(__file__).parent / "calls"
AGENT_NAME = "patient-tester"


def parse_job_metadata(raw: str | None) -> tuple[str, str]:
    """Returns (scenario_path, call_id) from the dispatch metadata run.py
    sets (see run.py's LiveKitApiCallClient.dispatch_agent). `call_id` is
    also the folder name under calls/, and matches the room name run.py
    used, so an orchestrator-side outcome (run_result.json) and the
    agent-side artifacts (transcript/audio/metadata.json) always land in the
    same place even across a batch of same-scenario calls.

    Falls back to VOICEBOT_DEFAULT_SCENARIO for local `agent.py console`
    testing, where there's no real dispatch metadata.
    """
    if raw:
        try:
            payload = json.loads(raw)
            return payload["scenario_path"], payload["call_id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    fallback_scenario = os.environ.get("VOICEBOT_DEFAULT_SCENARIO")
    if not fallback_scenario:
        raise RuntimeError(
            "Job was dispatched without valid {'scenario_path','call_id'} "
            "metadata, and no VOICEBOT_DEFAULT_SCENARIO fallback is set for "
            "local testing"
        )
    return fallback_scenario, f"console-{int(time.time())}"


async def _embed_fn(text: str) -> np.ndarray:
    """OpenAI embeddings, adapted to the async signature rag.py expects."""
    model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    result = await openai.embeddings.create_embeddings(input=[text], model=model)
    return np.array(result[0].embedding, dtype="float32")


class PatientCaller(Agent):
    """The caller persona: improvises within the scenario brief (see
    scenario_loader.Scenario.build_system_prompt), optionally grounded by a
    per-turn RAG lookup into a longer patient history (docs/DECISIONS.md #9).
    """

    def __init__(self, scenario: Scenario, history_index: PatientHistoryIndex | None):
        super().__init__(instructions=scenario.build_system_prompt())
        self._history_index = history_index

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        if self._history_index is None:
            return
        query = (new_message.text_content or "").strip()
        if not query:
            return
        chunks = await self._history_index.retrieve(query, top_k=3)
        if not chunks:
            return
        history_text = "\n".join(f"- {chunk}" for chunk in chunks)
        turn_ctx.add_message(
            role="system",
            content=(
                "Relevant excerpts from your own patient history (only bring "
                "these up if they're naturally relevant to what was just "
                f"said):\n{history_text}"
            ),
        )


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    scenario_path, call_id = parse_job_metadata(ctx.job.metadata)
    scenario = load_scenario(scenario_path)
    logger.info("Starting call for scenario %s", scenario.slug)

    history_index = None
    if scenario.patient_record_path is not None:
        history_index = await PatientHistoryIndex.from_markdown_file(
            scenario.patient_record_path, embed_fn=_embed_fn
        )

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", sample_rate=SAMPLE_RATE),
        llm=openai.LLM(model=os.environ.get("OPENAI_LLM_MODEL", "gpt-4o-mini")),
        tts=cartesia.TTS(voice=os.environ.get("CARTESIA_VOICE_ID") or None),
        vad=silero.VAD.load(sample_rate=SAMPLE_RATE),
        turn_detection=inference.TurnDetector(),
    )

    run_dir = CALLS_DIR / call_id
    run_dir.mkdir(parents=True, exist_ok=True)

    recorder = DualTrackRecorder(sample_rate=SAMPLE_RATE)
    transcript_writer = TranscriptWriter(scenario_name=scenario.slug)
    call_start = time.monotonic()
    capture_tasks: list[asyncio.Task] = []

    async def _capture_track(track: rtc.Track, sink) -> None:
        stream = rtc.AudioStream.from_track(
            track=track, sample_rate=SAMPLE_RATE, num_channels=1
        )
        try:
            async for event in stream:
                sink(bytes(event.frame.data))
        finally:
            await stream.aclose()

    def _on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info("Recording remote audio from %s", participant.identity)
            capture_tasks.append(
                asyncio.create_task(_capture_track(track, recorder.write_agent_frame))
            )

    def _on_local_track_published(publication, track):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info("Recording our own published audio")
            capture_tasks.append(
                asyncio.create_task(_capture_track(track, recorder.write_caller_frame))
            )

    ctx.room.on("track_subscribed", _on_track_subscribed)
    ctx.room.on("local_track_published", _on_local_track_published)

    def _on_conversation_item_added(event) -> None:
        item = event.item
        if not isinstance(item, llm.ChatMessage) or item.role not in ("user", "assistant"):
            return
        text = item.text_content
        if not text:
            return
        # "user" = STT transcript of the practice's phone agent; "assistant" =
        # our own persona's LLM/TTS turn.
        speaker = "agent" if item.role == "user" else "caller"
        transcript_writer.add_turn(speaker, text, time.monotonic() - call_start)

    session.on("conversation_item_added", _on_conversation_item_added)

    await session.start(
        agent=PatientCaller(scenario, history_index),
        room=ctx.room,
        room_input_options=RoomInputOptions(audio_enabled=True),
    )

    max_seconds = float(os.environ.get("MAX_CALL_SECONDS", "240"))

    async def _finalize(*_args) -> None:
        for task in capture_tasks:
            task.cancel()
        wav_path = recorder.finalize(run_dir / "audio.wav")
        output_format = os.environ.get("AUDIO_OUTPUT_FORMAT", "ogg")
        compressed_path: Path | None = None
        try:
            compressed_path = convert_to_compressed(wav_path, output_format=output_format)
        except Exception:
            logger.exception("ffmpeg conversion failed; keeping audio.wav only")

        transcript_writer.write(run_dir)
        metadata = {
            "call_id": call_id,
            "scenario_file": str(scenario.source_path),
            "scenario_slug": scenario.slug,
            "run_dir": str(run_dir),
            "duration_seconds": time.monotonic() - call_start,
            "audio_file": str(compressed_path) if compressed_path else str(wav_path),
            "stt": "deepgram/nova-3",
            "llm": os.environ.get("OPENAI_LLM_MODEL", "gpt-4o-mini"),
            "tts": "cartesia/sonic-2",
        }
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        logger.info("Call artifacts written to %s", run_dir)

    ctx.add_shutdown_callback(_finalize)

    async def _enforce_max_duration() -> None:
        await asyncio.sleep(max_seconds)
        logger.warning("Max call duration (%ss) reached; ending call", max_seconds)
        await ctx.delete_room()

    asyncio.create_task(_enforce_max_duration())


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=AGENT_NAME))
