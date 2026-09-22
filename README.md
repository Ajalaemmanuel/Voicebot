# AI Patient Test Caller

A Python voice bot, built on **LiveKit Agents in pipeline mode** (separate
STT / LLM / TTS — no realtime/speech-to-speech model, no hosted voice
platform), that calls a fixed test line and plays a "patient" persona to
stress-test a practice's AI phone agent. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for how it works and why, and [`docs/`](docs/) for the full requirements,
design, and decision log.

**Test line called by this bot: `+1-805-439-8008` only.**

## 1. Prerequisites

- Python 3.10+
- [`ffmpeg`](https://ffmpeg.org/download.html) on your `PATH` (used to convert
  the raw call recording to OGG/MP3)
- Accounts (free/trial tiers are enough for this project's call volume):
  - [LiveKit Cloud](https://cloud.livekit.io/) — hosting + SIP for the room
  - [Twilio](https://www.twilio.com/) — outbound SIP trunk to actually dial
    the PSTN test number
  - [Deepgram](https://deepgram.com/) — STT
  - [OpenAI](https://platform.openai.com/) — LLM + embeddings
  - [Cartesia](https://cartesia.ai/) — TTS

These accounts have to be created and funded by you — an AI assistant can't
sign up for third-party services on your behalf. Twilio in particular is a
real phone carrier and will charge (small, per-minute) fees once you place
calls.

## 2. Telephony setup (one-time)

1. Create a LiveKit Cloud project. Note the project URL, API key, and API
   secret (Settings → Keys).
2. In Twilio, create an **Elastic SIP Trunk** (Twilio Console → Elastic SIP
   Trunking → Trunks → Create new). Under that trunk:
   - **Termination**: note the termination SIP URI
     (`your-trunk.pstn.twilio.com`).
   - **Origination**: add LiveKit's SIP signaling address as an origination
     URI so Twilio will accept calls *from* LiveKit
     (see LiveKit's [SIP trunk setup guide](https://docs.livekit.io/sip/quickstarts/configuring-sip-trunk/)
     for the exact current origination URI/IP to whitelist — LiveKit
     publishes this per-region).
   - Add authentication (either IP allowlisting or username/password
     credentials — either works, just note which one you configure).
   - Buy or port in a number if you don't already have one to place the
     calls *from* (the number Twilio uses as caller ID); it doesn't need to
     be the test line itself.
3. Register that Twilio trunk as a LiveKit **SIP outbound trunk**. Install
   the [`lk` CLI](https://github.com/livekit/livekit-cli), then:

   ```bash
   lk sip outbound create trunk.json
   ```

   where `trunk.json` looks like:

   ```json
   {
     "trunk": {
       "name": "twilio-outbound",
       "address": "your-trunk.pstn.twilio.com",
       "numbers": ["+1XXXXXXXXXX"],
       "auth_username": "your-twilio-trunk-username",
       "auth_password": "your-twilio-trunk-password"
     }
   }
   ```

   The command prints a trunk ID like `ST_xxxxxxxxxxxx` — put that in
   `SIP_OUTBOUND_TRUNK_ID` in your `.env` (step 3 below).

## 3. Local setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
copy .env.example .env         # Windows
# cp .env.example .env         # macOS/Linux
```

Fill in every value in `.env`: LiveKit URL/key/secret, the SIP outbound
trunk ID from step 2, and your Deepgram/OpenAI/Cartesia API keys.

## 4. Run the tests

```bash
pytest
```

This covers all the logic that doesn't require a live call or a paid API —
scenario parsing, RAG chunking/retrieval, transcript formatting, WAV
recording, and call orchestration control flow (with the LiveKit API
mocked). See `docs/DECISIONS.md` #10 for what's deliberately *not* covered
by these tests (the live SIP call itself).

## 5. Sanity-check the persona locally (no telephony, no cost)

```bash
python agent.py console
```

This uses LiveKit's built-in console mode to talk to the caller persona
through your own mic/speakers, so you can check the prompt, RAG retrieval,
and TTS voice sound right before spending any Twilio minutes. Press Ctrl+C
to stop.

## 6. Place one real call — single command (F8)

```bash
python run.py --scenario scenarios/simple_scheduling_1.yaml
```

This starts the agent worker, creates a room, dispatches the worker into it,
waits until it's actually joined, then dials `+1-805-439-8008` via the SIP
trunk. When the call ends (or hits `MAX_CALL_SECONDS`, default 240s), you'll
find the results in:

```
calls/simple_scheduling_1-<8-char-id>/
  audio.ogg          # both sides of the call
  transcript.txt      # human-readable, timestamped
  transcript.json      # structured, same data
  metadata.json         # scenario, providers/models used, duration (written by agent.py)
  run_result.json        # outcome/duration/error as seen by the orchestrator (written by run.py)
```

## 7. Run the full batch (10+ calls, F9)

```bash
python run_batch.py --scenarios scenarios/*.yaml --gap 30
```

Runs every scenario in `scenarios/` one at a time, waiting 30s between
calls, and prints a summary table at the end. A failed call (no answer, SIP
error) doesn't stop the rest of the batch — see `docs/TECHNICAL_DESIGN.md`
"Failure modes" for exactly how each case is handled.

## 8. Project layout

```
agent.py              # LiveKit Agents worker: the caller persona (STT/LLM/TTS/VAD/turn-detector)
call_runner.py          # testable call orchestration control flow (used by run.py/run_batch.py)
recorder.py              # dual-track in-process audio capture -> WAV -> OGG/MP3
rag.py                    # patient-history chunking + per-turn retrieval
transcript.py              # timestamped transcript writer
scenario_loader.py           # scenario YAML schema + system-prompt builder
run.py                         # single-call CLI
run_batch.py                    # batch CLI
scenarios/                       # scenario briefs (+ patient_record.md for a few)
tests/                             # pytest suite (see docs/DECISIONS.md #10)
calls/                               # call outputs land here
bug_report/BUGS.md                    # findings from listening to real calls
docs/                                   # PRD, requirements, technical design, decisions log
```

## Notes

- All calls must go to the fixed test number above — `run.py`/`run_batch.py`
  read it from `TEST_LINE_NUMBER` in `.env`, which defaults to it; don't
  point it elsewhere for submission calls.
- If a call fails outright (no answer, SIP auth rejected), check
  `run_result.json` in that call's folder for the recorded `outcome`/`error`
  before assuming the practice's agent is at fault.

## 9. Web dashboard (optional)

[`web/`](web/) is a separate, read-only Next.js dashboard for browsing
scenarios, call transcripts/recordings, and the bug report in a browser,
deployable to AWS Amplify Hosting. It holds no provider credentials and
places no calls — see [`web/README.md`](web/README.md) for local dev and
deployment steps, and [`docs/SECURITY.md`](docs/SECURITY.md) for the
security reasoning behind that split.
