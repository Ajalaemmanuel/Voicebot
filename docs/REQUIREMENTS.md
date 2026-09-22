# System Requirements

## Functional requirements

| ID | Requirement |
|----|-------------|
| F1 | The system must place an outbound call to the fixed test number `+1-805-439-8008` over PSTN. |
| F2 | The system must use separate STT, LLM, and TTS components (pipeline mode) — no realtime/speech-to-speech model, no hosted voice-agent platform. |
| F3 | The system must run in LiveKit Agents (Python). |
| F4 | The system must support multiple call **scenarios**, each defining a patient persona, a goal, and (optionally) an edge-case instruction, loaded from a config file without code changes. |
| F5 | The system must support an optional longer **patient history** per scenario, retrieved (not fully prompted) turn-by-turn via RAG. |
| F6 | The system must record every call's full audio (both sides) to a local file, convertible to OGG or MP3. |
| F7 | The system must produce a timestamped, speaker-labeled transcript for every call, in a format that supports citing "transcript-N.txt at MM:SS". |
| F8 | The system must be runnable end-to-end for one call via a single command after one-time setup. |
| F9 | The system must support running a batch of scenarios sequentially without manual intervention between calls. |
| F10 | The system must hang up / tear down the call automatically if it exceeds a configured maximum duration (safety against runaway cost). |
| F11 | The system must not silently swallow a failed call (SIP rejected, trunk misconfigured, no answer) — it must surface the failure clearly, distinctly from a normal call. |

## Non-functional requirements

| ID | Requirement | Notes |
|----|-------------|-------|
| N1 | **Latency**: end-of-caller-turn to start-of-our-TTS-audio should target well under ~1.5s under normal conditions. | Two AI agents talking back to back means latency on *both* sides is audible; see `docs/DECISIONS.md` for provider choices made for this reason. |
| N2 | **Call length**: a "good" call is 1-3 minutes; the system enforces a hard ceiling (default 240s, configurable) per F10. | Caps API/telephony cost per call and avoids stuck calls. |
| N3 | **Cost**: default configuration should keep per-call cost low (cheap-tier LLM, pay-as-you-go STT/TTS, no idle infra). | Twelve ~2-minute calls should cost low single-digit dollars in API/telephony usage, not counting any free trial credit. |
| N4 | **Resilience**: a dropped call, a SIP auth failure, or an unanswered call must not corrupt or block subsequent runs in a batch. | `run_batch.py` must continue to the next scenario even if one call fails. |
| N5 | **Reproducibility**: the exact scenario, provider config, and code version used for a given call must be recoverable from its output folder. | `metadata.json` per call records scenario file, git commit (if available), timestamps, providers/models used. |
| N6 | **No cloud storage dependency**: recording must not require provisioning an S3/GCS/Azure bucket. | See "Recording approach" tradeoff in `docs/DECISIONS.md`. |
| N7 | **Testability**: all logic that doesn't require a live phone call (scenario parsing, RAG retrieval, transcript formatting, WAV writing, call-orchestration control flow) must be unit-testable without network access or paid API calls. | Achieved via TDD with mocked externals; see `docs/DECISIONS.md` and `tests/`. |
| N8 | **Portability**: development happens on Windows; the code must not assume a Unix-only environment (path handling, subprocess calls to `ffmpeg`, etc.). | |

## Explicit constraints (from the assignment)

- Must be Python, using LiveKit Agents.
- Must NOT use realtime/speech-to-speech models (OpenAI Realtime API, LiveKit
  RealtimeModel plugins, Gemini Live, etc.).
- Must NOT use hosted voice-agent platforms (Vapi, Retell, Bland, etc.).
- All test calls must go to the fixed number `+1-805-439-8008` only.
- Minimum 10 full recorded calls (1-3 min each), both sides, submitted as
  OGG or MP3 plus transcript.
