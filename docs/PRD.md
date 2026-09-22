# PRD — AI Patient Test Caller

## Problem

A medical practice has deployed an AI phone agent that handles patient calls
(scheduling, rescheduling, refills, hours/insurance questions). Before real
patients rely on it, we need evidence of how it behaves under realistic and
adversarial conditions — not just "does it answer the phone" but "does it
give correct, safe answers, handle interruptions gracefully, and fail
sensibly when a caller is unclear or asks for something invalid (e.g. a
weekend appointment at a practice that's closed weekends)."

Manually calling and testing this by hand doesn't scale and isn't
repeatable. We need an automated caller that can hold a real, coherent voice
conversation with the practice's agent, in a variety of scenarios, and leave
behind evidence (recording + transcript) a human can review.

## Goal

Build a Python voice bot ("the tester") that places outbound calls to a
fixed test line (+1-805-439-8008), plays a believable patient persona for a
given scenario, converses naturally for 1-3 minutes, and produces a
timestamped transcript plus an audio recording of every call.

## Non-goals

- We are not building or modifying the practice's phone agent itself — it's
  a black box under test.
- We are not building a production/scalable calling platform — this is a
  test-harness for a fixed number of one-off calls against one number.
- We are not doing real-time/speech-to-speech voice AI (excluded by the
  assignment) — see `docs/DECISIONS.md` for why pipeline mode was chosen
  even where realtime models might otherwise be tempting.
- We are not building a general-purpose telephony product; the SIP/telephony
  wiring here is scoped to "one outbound number, one trunk provider."

## Users

- **Us (the submitter)**: runs the bot to generate call evidence, then
  reviews it to write bug reports.
- **The reviewer**: reads the transcripts/recordings, README, architecture
  doc, and bug report to judge whether the practice's agent (and our tester)
  work.

## Success criteria

1. The bot holds a coherent voice conversation with the practice's agent —
   this is the primary bar; everything else is judged only if this is met.
2. At least 10 complete calls (1-3 minutes each), each with both a
   transcript and an OGG/MP3 recording, spanning:
   - Simple appointment scheduling
   - Rescheduling / canceling
   - Medication refill requests
   - Office hours / location / insurance questions
   - Edge cases: interruptions, unclear/mumbled requests, invalid requests
     (e.g. weekend booking), conflicting information
3. A bug report (`bug_report/BUGS.md`) with well-described, real findings —
   not a long list of nitpicks.
4. Documentation (README, ARCHITECTURE, this PRD, REQUIREMENTS,
   TECHNICAL_DESIGN, DECISIONS) that lets a reviewer understand what was
   built and *why* without reading all the code.
5. Evidence of iteration: at least one instance where an early call surfaced
   a problem with our own bot (not the practice's agent) and we changed the
   prompt/config/code in response.

## Scope for this submission

12 scenario briefs (2 buffer calls over the 10 minimum), a single-command
runner per call plus a batch runner, in-process recording + transcription (no
external cloud storage dependency), and a RAG-backed patient history for
scenarios where a longer, referenceable history makes the persona more
realistic (see `docs/DECISIONS.md` for the RAG tradeoff discussion).
