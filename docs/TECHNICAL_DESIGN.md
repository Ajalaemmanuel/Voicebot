# Technical Design

## Component overview

```
                     ┌─────────────────────────────────────────────────────┐
                     │                  LiveKit Cloud room                  │
                     │                                                       │
 Twilio Elastic      │   ┌───────────────┐        ┌────────────────────┐   │
 SIP Trunk  ───SIP──▶│──▶│ SIP participant│◀──────▶│   our AgentSession  │   │
 (PSTN bridge to     │   │ (practice's    │  audio  │  (agent.py)         │   │
  +1-805-439-8008)   │   │  phone agent)  │         │                     │   │
                     │   └───────────────┘        │  VAD → STT → LLM → TTS │   │
                     │                              │  + RAG hook          │   │
                     │                              └──────────┬──────────┘   │
                     └─────────────────────────────────────────┼──────────────┘
                                                                │
                                        ┌───────────────────────┼───────────────────────┐
                                        ▼                                              ▼
                               recorder.py (dual-track                      transcript.py (session
                               AudioStream capture → WAV                    events → transcript.txt /
                               → ffmpeg → OGG/MP3)                          transcript.json)
```

`run.py` is the orchestrator that sits outside the room: it starts the agent
worker, creates the room, explicitly dispatches the worker into it with the
chosen scenario as job metadata, and calls the LiveKit SIP API to dial the
test line into that same room. `run_batch.py` calls that same logic in a loop
over multiple scenarios.

## Per-turn data flow

1. Practice agent speaks → audio arrives on the SIP participant's track.
2. `recorder.py`'s `AudioStream` on that track writes PCM frames to the WAV
   file (right channel) as they arrive, independent of anything else.
3. Deepgram STT (subscribed to the same track via `AgentSession`) streams
   interim transcripts; the turn-detector plugin + Silero VAD decide when the
   utterance is complete.
4. On end-of-turn, `Agent.on_user_turn_completed(turn_ctx, new_message)` runs
   (see `agent.py`): if the active scenario has a `patient_record`, we embed
   the just-finalized user message text, retrieve the top-k chunks from
   `rag.py`'s in-memory index, and append them to `turn_ctx` as a system
   message before the LLM call. `transcript.py`'s listener also records the
   finalized user turn with a timestamp.
5. The LLM (`gpt-4o-mini`) streams a reply given the scenario system prompt +
   (optionally) retrieved history + conversation so far.
6. TTS (Cartesia) streams audio for the reply as tokens arrive; `AgentSession`
   publishes that audio to our local participant's track.
7. `recorder.py` also captures our own published track's frames (left
   channel) as they're generated, and `transcript.py` records the finalized
   agent turn with a timestamp once TTS playback of that turn completes.
8. Repeat until the call ends (SIP participant disconnects) or
   `MAX_CALL_SECONDS` is reached, whichever first — `run.py` force-ends the
   room in the latter case.
9. On room shutdown, `recorder.py` finalizes and closes the WAV file, then
   shells out to `ffmpeg` to produce `audio.ogg` (or `.mp3`); `transcript.py`
   flushes `transcript.txt` and `transcript.json`; `run.py` writes
   `metadata.json` (scenario file used, start/end time, providers/models,
   git commit if available, call outcome).

## `run.py` lifecycle

```
parse args (--scenario path, --format ogg|mp3, --max-seconds)
  → load + validate scenario (scenario_loader.py)
  → ensure agent worker process is running (spawn `python agent.py start` if not)
  → create LiveKit room (unique name: <scenario-slug>-<timestamp>)
  → explicit agent dispatch into that room, metadata = scenario path
  → CreateSIPParticipant(room, TEST_LINE_NUMBER, trunk=SIP_OUTBOUND_TRUNK_ID)
  → poll room state until: SIP participant leaves, agent leaves, or timeout
  → on timeout: DeleteRoom (forces both participants out, ends the call)
  → write metadata.json, confirm audio.ogg/mp3 + transcript.* exist in calls/<run-id>/
  → exit 0 on a normal call, non-zero + clear message on failure (F11)
```

`run_batch.py` wraps this per scenario file in `scenarios/*.yaml`, sleeping
`--gap` seconds between calls, continuing to the next scenario if one call
fails (N4), and printing a summary table at the end.

## Failure modes and handling

| Failure | Detection | Handling |
|---|---|---|
| SIP trunk/auth misconfigured | `CreateSIPParticipant` raises / returns error status | `run.py` exits non-zero with the raw error surfaced, room is cleaned up, no partial `calls/` folder is left half-written (metadata written last, only on a real attempt). |
| Test line doesn't answer | SIP participant never reaches `active` state within a short answer-timeout | Treated as a failed call, logged distinctly from a normal completed call in `metadata.json` (`"outcome": "no_answer"`), `run_batch.py` continues. |
| Call exceeds max duration | Wall-clock check in `run.py`'s poll loop | Room is deleted, `metadata.json` records `"outcome": "timeout"`; whatever transcript/audio was captured up to that point is still finalized and kept (real duration, not silently discarded). |
| STT/LLM/TTS API error mid-call | Exception surfaced from the relevant LiveKit plugin | The agent apologizes/ends the turn gracefully where the framework allows it; the call is otherwise allowed to continue rather than aborting the whole run, since a single degraded turn is still useful evidence. |
| Recording write failure (disk, permissions) | Exception in `recorder.py` | Call still completes conversationally; `metadata.json` records the recording failure so the gap is visible, rather than silently producing an empty file. |

## Config surface

All of the above is controlled via `.env` (see `.env.example`) plus per-call
CLI flags on `run.py`/`run_batch.py`; no code changes are needed to add a new
scenario, switch TTS provider, or change the call-duration ceiling.
