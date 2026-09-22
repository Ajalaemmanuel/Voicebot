# Decisions & Tradeoffs

One entry per non-trivial choice: what we picked, what else we considered,
why we rejected the alternatives, and what tradeoff we accepted. This is the
place to read *why*, without digging through code. `ARCHITECTURE.md` stays
short and links back here.

---

## 1. Pipeline mode instead of a realtime speech-to-speech model

**Decision**: separate STT → LLM → TTS stages via LiveKit Agents'
`AgentSession`, no realtime/speech-to-speech model.

**Alternatives considered**: OpenAI Realtime API, Gemini Live, LiveKit's own
`RealtimeModel` plugins — all give lower latency and more natural prosody
because one model handles audio-in to audio-out directly.

**Why rejected**: explicitly disallowed by the assignment. Independent of
that rule, pipeline mode also gives us clean intermediate text (STT output,
LLM output) to log as a transcript and to hook RAG retrieval into — a
realtime model's internal reasoning isn't directly observable that way.

**Tradeoff accepted**: higher end-to-end latency and a small naturalness
gap versus realtime models, offset by choosing low-latency components at
each stage (see #2-#4) and by LiveKit Agents' pipelining (STT interim
results, streaming LLM tokens into streaming TTS) rather than a fully
serial request/response chain.

---

## 2. STT: Deepgram `nova-3` (streaming)

**Alternatives considered**:
- **OpenAI Whisper (API or local)** — excellent accuracy, but the hosted API
  is not designed for low-latency streaming partials, and local Whisper on a
  laptop CPU is too slow for real-time phone audio without a GPU.
- **AssemblyAI streaming** — comparable quality/latency to Deepgram; would
  have worked equally well.
- **Local/open-source dictation stacks** (e.g. the `whisper.cpp`-based tools
  referenced in early research — Handy, OpenWhispr) — good for a local
  dictation UI where you control the mic and can tolerate short buffering,
  but they're built for single-user local dictation, not telephone-grade
  8kHz streaming with barge-in, and add GPU/runtime setup complexity we
  don't need for a hosted test harness.

**Why Deepgram**: mature LiveKit Agents plugin, proven with 8kHz phone audio,
strong streaming interim results (needed for the turn-detector to work
well), competitive pricing/free credit for this call volume.

**Tradeoff accepted**: a per-minute cloud cost and a network dependency,
versus a local/offline option. Acceptable since we already depend on
cloud LLM/TTS/telephony for this project.

---

## 3. LLM: OpenAI `gpt-4o-mini`

**Alternatives considered**:
- **Anthropic Claude (e.g. Sonnet)** — very strong instruction-following and
  persona consistency; would also satisfy "not realtime."
- **A larger/more expensive model** (GPT-4.1, Claude Opus) — better
  reasoning and edge-case creativity, at meaningfully higher cost and
  latency per turn.

**Why gpt-4o-mini**: the caller side doesn't need frontier reasoning — it
needs to reliably follow a persona brief, improvise naturally, and
occasionally execute a specific edge-case instruction (interrupt, mumble,
ask for a Sunday slot). `gpt-4o-mini` is fast and cheap enough to run 12+
multi-turn calls without material cost, and in practice follows short,
well-structured system prompts reliably. Also reused for RAG embeddings
(`text-embedding-3-small`), keeping the number of provider accounts down.

**Tradeoff accepted**: somewhat less creative/robust edge-case behavior than
a frontier model. Mitigated by writing explicit, concrete edge-case
instructions per scenario rather than relying on the model to invent
mischief unprompted.

---

## 4. TTS: Cartesia `sonic-2`

**Alternatives considered**:
- **ElevenLabs** — noticeably natural prosody and pacing (this is why it was
  raised in early research notes); its Flash/Turbo streaming models bring
  latency down but still trail Cartesia's time-to-first-audio-byte.
- **OpenAI TTS / Deepgram Aura** — solid, but Cartesia had the best
  documented latency numbers among LiveKit-supported TTS plugins at the time
  of building this.

**Why Cartesia**: this project has two AI agents talking back-to-back —
*our* TTS latency and the practice agent's response latency both stack into
the perceived pause between turns. Cartesia's low time-to-first-byte
directly reduces that, and Sonic-2 voices are natural enough for a phone
call use case (not a narration/audiobook use case, where ElevenLabs' edge
would matter more).

**Tradeoff accepted**: marginally less natural-sounding prosody than
ElevenLabs. Deliberately not treated as a blocker since call intelligibility
and turn-taking speed matter more than voice acting quality for this task.
The TTS backend is a single config value (`tts.py` factory), so swapping to
ElevenLabs for a future comparison is a small change, not a rewrite.

---

## 5. VAD + turn detection: Silero VAD + LiveKit's hosted semantic turn detector

**Alternatives considered**:
- VAD-only endpointing (fixed silence timeout).
- The older `livekit-plugins-turn-detector` package (a locally-run semantic
  end-of-utterance model) — now deprecated by LiveKit in favor of
  `livekit.agents.inference.TurnDetector`, a hosted equivalent that ships in
  `livekit-agents` core (no extra model download/plugin dependency, and it
  authenticates with the same LiveKit Cloud credentials we already need).

**Why rejected (VAD-only)**: a fixed silence timeout either cuts off a
speaker mid-thought (too short) or makes the conversation feel sluggish
(too long) — and it's especially bad here because *our own* TTS output can
have natural micro-pauses that a naive VAD-only endpointer would
misinterpret as end-of-turn.

**Why `inference.TurnDetector`**: it's a small semantic model that looks at
the actual partial transcript to judge whether an utterance sounds
complete, on top of VAD — meaningfully reduces both false interruptions and
awkward dead air, which matters for judging "did the bot hold a coherent
conversation" (the #1 review criterion). Using LiveKit's current hosted
version instead of the deprecated local plugin avoids taking a dependency on
a package LiveKit itself is phasing out.

**Tradeoff accepted**: one more network round-trip per turn for the
semantic check (hosted, not local), worth it for conversational coherence
and for staying on the currently-supported API.

---

## 6. Telephony: LiveKit Cloud SIP + Twilio Elastic SIP Trunk

**Alternatives considered**:
- **Self-hosting a SIP server** (e.g. FreeSWITCH/Kamailio/drachtio) in front
  of LiveKit — full control, but a large amount of infra to stand up and
  operate correctly (NAT traversal, codecs, security) for a project whose
  actual telephony need is "dial one number a dozen times."
- **A different SIP trunk provider** (Telnyx, Bandwidth, etc.) — would work
  equally well technically; Twilio was picked for documentation maturity and
  because it's the most common pairing referenced in LiveKit's own SIP
  guides, minimizing setup risk.

**Why LiveKit Cloud + Twilio**: LiveKit Cloud has native SIP support (no
server to run ourselves), a generous free tier for this call volume, and a
documented outbound-trunk + `CreateSIPParticipant` flow that lets a normal
Python script dial a PSTN number into a room our agent is already in.

**Tradeoff accepted**: dependency on two external accounts (LiveKit Cloud,
Twilio) with real (if small) per-minute PSTN cost, and setup steps the user
must perform manually (an AI assistant can't create/fund third-party
accounts) — documented step-by-step in `README.md`.

---

## 7. Recording: in-process dual-track capture, not LiveKit Egress

**Alternatives considered**: LiveKit Room Composite Egress writing directly
to a file.

**Why rejected**: LiveKit Cloud's Egress requires an upload destination
(S3/GCS/Azure Blob) — it doesn't write to local disk on a cloud project.
That means provisioning and paying for a cloud storage bucket just to get a
recording, for a project that only needs ~12 short local audio files.

**Why in-process capture instead**: our own Python process already has
`rtc.AudioStream` access to both the remote (practice agent) track and our
own published (TTS) track. Writing both to a stereo WAV as they arrive,
then shelling out to `ffmpeg` for a WAV→OGG/MP3 pass, needs no extra cloud
account and keeps the recording colocated with the transcript it must be
cited against.

**Tradeoff accepted**: we own the muxing/timing code ourselves (tested in
`tests/test_recorder.py`) instead of delegating to a managed service, and
recording quality depends on our process staying alive and not dropping
frames — acceptable for calls capped at 4 minutes.

---

## 8. Scenario format: YAML brief + LLM improvisation, not scripted turns

**Decision**: each scenario is a short YAML persona/goal/edge-case brief
injected into the caller LLM's system prompt; the LLM improvises the actual
words rather than following a fixed line-by-line script.

**Why rejected (scripted turns)**: a fixed script can't adapt to whatever
the practice's agent actually says (which questions it asks, in what order,
using what phrasing) — it would produce stilted, obviously-scripted-sounding
calls and couldn't opportunistically probe a bug it stumbles into.

**Tradeoff accepted**: slightly less control over exactly what gets said and
when (mitigated by explicit, concrete edge-case instructions per scenario,
and by listening to early calls and tightening prompts — see the iteration
notes in `ARCHITECTURE.md`).

---

## 9. RAG-backed patient history for select scenarios

**Alternatives considered**:
- **No RAG — everything in the system prompt.** Simpler, but a genuinely
  rich patient history (multiple past visits, prescriptions, allergies,
  family members) either bloats every single LLM call with mostly-irrelevant
  detail, or gets trimmed down to the point where it's not meaningfully
  richer than a one-line persona blurb.
- **A real vector database** (Chroma, pgvector, Pinecone) — unnecessary
  operational weight for a handful of scenarios with a few dozen chunks
  each; adds a service dependency with no accuracy benefit at this scale.

**Why per-turn retrieval with plain in-memory cosine similarity**: for
scenarios where a longer `patient_record.md` exists, we chunk it once at
session start, embed each chunk (`text-embedding-3-small`), and on every
turn embed the practice agent's latest utterance and pull the top 2-3
relevant chunks into context via `Agent.on_user_turn_completed`. This gives
the persona specific, realistic details (an exact past prescription date, a
specific prior complaint) only when relevant, rather than every turn, and it
stress-tests whether the practice's agent can handle a caller referencing a
real history. A few dozen vectors held in a Python list and compared with
`numpy` is plenty fast — no vector DB needed.

**Tradeoff accepted**: retrieval quality depends on embedding the *practice
agent's* utterance as the query, which works well for direct questions
("when did you last request a refill?") but less well for open-ended
prompts ("how can I help you?") — acceptable since those turns don't need
history injected anyway. Only scenarios where a longer history adds
realistic value (reschedule, refill, insurance, one conflicting-info edge
case) carry a `patient_record.md`; simple scheduling/hours scenarios
deliberately skip RAG to stay simple and cheap, per requirement F5's "not
fully prompted" framing.

---

## 10. Testing strategy: TDD on our logic, not on the live phone call

**Decision**: apply TDD (write the failing test first) to every module that
doesn't require a live call or paid API — scenario parsing, RAG chunking and
ranking (embeddings mocked), transcript formatting, WAV recording/muxing,
and call-orchestration control flow (LiveKit API client mocked). The live
SIP call itself is exercised only by the real verification calls, not unit
tests.

**Why**: there's no local mock IVR to call, and mocking the entire LiveKit
SIP/room stack to "unit test" a live call would mostly test our mocks, not
real behavior — low value for real effort. The logic that *is* ours and
*doesn't* need the network (parsing, ranking, formatting, muxing,
orchestration control flow) is exactly the kind of thing TDD is good at:
fast feedback, regression safety, and a spec you can read.

**Tradeoff accepted**: the riskiest part of the system (does the SIP dial
actually work, does the conversation actually stay coherent) is validated
by manual/real verification calls, not automated tests — an explicit,
documented scope boundary rather than a false sense of coverage from mocking
too deep.
