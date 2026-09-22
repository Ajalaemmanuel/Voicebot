# Bug Report — Practice AI Phone Agent

Findings from listening to the recorded calls under `calls/` and reading
their transcripts. Entries follow the format below; only real, verified
issues are listed here — this file is populated/updated after each batch of
calls, not written in advance of them.

## Entry format

```
Bug: <one-line description>
Severity: <High | Medium | Low>
Call: <transcript file>.txt at <MM:SS>
Details: <what happened, what should have happened instead>
```

### Example (from the assignment brief, for format reference only)

```
Bug: Agent confirms appointment for Sunday, but the practice is closed on
weekends
Severity: High
Call: transcript-07.txt at 1:23
Details: When asked "Can I come in Sunday at 10am?", the agent responded,
"I've scheduled you for Sunday at 10 am" without checking office hours.
Should have informed the patient the office is closed on weekends and
offered the next available weekdays.
```

`scenarios/edge_weekend_request.yaml` is designed to specifically probe for
exactly this failure mode.

---

## Findings

_(pending: to be filled in after listening to the actual recorded calls —
see `calls/` for the raw transcripts/recordings once the batch has been run.)_

## Scenario coverage checklist

- [ ] `simple_scheduling_1` — Simple Scheduling - Annual Checkup
- [ ] `simple_scheduling_2` — Simple Scheduling - New Patient Visit
- [ ] `reschedule` — Reschedule Existing Appointment
- [ ] `cancel` — Cancel Appointment
- [ ] `refill_request` — Medication Refill - Routine
- [ ] `refill_invalid_med` — Medication Refill - Not Actually Prescribed (safety boundary)
- [ ] `hours_location` — Office Hours and Location Questions
- [ ] `insurance_question` — Insurance Coverage Question
- [ ] `edge_interruption` — Interrupts the Agent
- [ ] `edge_unclear_mumble` — Unclear, Trailing-Off Requests
- [ ] `edge_weekend_request` — Requests a Sunday Appointment
- [ ] `edge_conflicting_info` — Conflicting Contact Info
