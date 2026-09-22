# Security Notes — Web Dashboard

The calling bot (`agent.py`, `run.py`, `run_batch.py`) needs real provider
credentials (LiveKit, Twilio, Deepgram, OpenAI, Cartesia) and only ever runs
as a trusted process you control — those secrets live in a local `.env`
(gitignored, never committed) and are never touched by the web dashboard.
This doc covers the **`web/` dashboard specifically**, since that's the part
meant to be reachable over the internet.

## The core decision: the dashboard needs zero secrets

Per the scope you chose, `web/` is a **read-only** viewer over content that's
already public in this repo (scenarios, call transcripts, recordings, the
bug report) — it does not place calls and does not talk to any of the STT/
LLM/TTS/telephony providers. Concretely:

- `web/scripts/sync-data.mjs` copies `scenarios/`, `calls/`, and
  `bug_report/BUGS.md` from the repo root into `web/data/` at build time.
- Every page and the `/audio/[callId]` route (`web/lib/data.ts`,
  `web/app/**`) reads only from that bundled `web/data/` directory via
  Node's `fs` — no network calls, no database, no AWS SDK, no API keys.
- `web/next.config.js` defines no environment variables at all, and nothing
  in the app is prefixed `NEXT_PUBLIC_` (the one Next.js mechanism that
  *would* ship a value into the browser bundle).

This is a deliberate "can't leak what isn't there" design: the biggest
category of accidental-secret-exposure bugs (a provider key ending up in
client-side JS, or a serverless function echoing `process.env`) isn't
possible here because the app never holds those secrets in the first place.
If a future version needs the dashboard to *trigger* calls, that crosses
into needing real secrets server-side — see "If you later add live-triggering"
below before building that.

## Access control

You chose to password-gate the whole dashboard rather than leave it public,
since the call data includes (fake, but realistic-looking) patient names and
DOBs. Do this at the **hosting platform**, not in application code:

- **AWS Amplify Hosting**: App settings → Access control → enable and set a
  username/password. This gate runs at the CDN/edge layer, in front of the
  app entirely — an unauthenticated request never reaches Next.js code, so
  there's no app-level auth logic to get wrong.
- Store that password only in the Amplify Console (or your password
  manager) — it isn't part of this repo and shouldn't be.

## AWS-side hardening checklist

- **No IAM credentials needed for the dashboard itself** — since it reads
  bundled files, not S3/a database, there's no AWS SDK client and therefore
  no access key to scope or rotate for this app. If you outgrow static
  bundling (e.g. calls/ gets too large to ship in every deploy) and move
  audio/transcripts to S3 instead, give the app a **least-privilege IAM
  role** (read-only, scoped to that one bucket/prefix) rather than a broad
  or account-level key, and keep the bucket's Block Public Access on.
- **HTTPS only** — Amplify Hosting serves everything over HTTPS/CloudFront
  by default; don't add a custom domain without keeping that.
- **.env hygiene** — `.env` (root) and `web/.env.local` are both gitignored.
  Verify with `git check-ignore -v .env web/.env.local` before ever running
  `git add -A`. Neither should ever be needed for `web/` per the design
  above; if one shows up, that's a signal scope has quietly grown into
  needing secrets and this doc should be revisited.
- **Dependency posture**: `npm audit` currently flags `postcss` (bundled
  transitively by Next.js 15.x) for CVEs that require processing
  attacker-controlled CSS/source maps — not applicable here since this app
  only ever builds its own source, but re-run `npm audit` and take the next
  Next.js stable minor/major once available, since the fix lands there.

## If you later add live-triggering from the web

You explicitly chose *view-only* for now — a public button that dials a real
phone number is a cost/abuse vector (anyone who reaches the page could run
up your Twilio bill or spam the test line) and needs more than a password
gate. Before building that, at minimum: per-user authentication (not a
shared password), server-side rate limiting per user/IP, the actual
provider secrets moved into a proper secrets manager (AWS Secrets Manager or
SSM Parameter Store, injected only into the backend process — never the
Next.js/browser layer), and a persistent backend (ECS/Fargate or similar)
to run `agent.py`'s worker, since Lambda-style serverless functions can't
host a long-lived LiveKit Agents process. Treat that as a separate,
follow-up design, not an incremental tweak to the current dashboard.
