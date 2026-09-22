# Architecture

This bot is a LiveKit Agents pipeline-mode worker: Deepgram nova-3 (STT) →
OpenAI gpt-4o-mini (LLM) → Cartesia sonic-2 (TTS), with Silero VAD and
LiveKit's hosted semantic turn detector deciding when the other party has
finished speaking. `run.py` creates a LiveKit room, explicitly dispatches the
worker into it, waits until the worker has actually joined, and only then
dials the fixed test line (+1-805-439-8008) via a Twilio-backed LiveKit SIP
outbound trunk — that ordering avoids dead air where the practice's agent
starts talking before our bot is listening. Once both parties are in the
room, the worker drives a caller persona (`agent.py`'s `PatientCaller`) built
from a per-scenario YAML brief (`scenarios/*.yaml`); for scenarios with a
richer fake patient history, a lightweight per-turn RAG lookup
(`rag.py`, embeddings via OpenAI) injects only the 2-3 most relevant history
chunks into context each turn, rather than dumping the whole record into
every prompt. Both sides of the call are captured directly in-process
(`recorder.py`, no cloud storage dependency) into a stereo WAV that's
converted to OGG/MP3, and every conversation turn is logged with a timestamp
(`transcript.py`) so bug reports can cite an exact `transcript-N.txt at
MM:SS`.

Provider and design choices — STT/LLM/TTS selection, why pipeline mode over
realtime, why LiveKit Cloud + Twilio for telephony, why recording is done
in-process instead of via LiveKit Egress, why RAG is scoped to a handful of
scenarios, and the TDD approach used to build the surrounding orchestration
logic — are each documented with alternatives and tradeoffs in
[`docs/DECISIONS.md`](docs/DECISIONS.md), which is the place to read *why*
without digging through the code. [`docs/TECHNICAL_DESIGN.md`](docs/TECHNICAL_DESIGN.md)
covers the detailed per-turn data flow and failure-mode handling, and
[`docs/PRD.md`](docs/PRD.md) / [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)
cover what's being built and why.

## Iteration notes

This section is filled in after real calls are made against the test line —
see [`bug_report/BUGS.md`](bug_report/BUGS.md) for the bugs found in the
practice's agent, and the entries below for problems found in *our own* bot
and the prompt/config changes made in response.

- _(pending: first batch of calls)_
