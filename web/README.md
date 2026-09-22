# Web Dashboard

A read-only Next.js dashboard over the calling bot's own output: scenario
briefs, call transcripts, audio playback, and the bug report. It does not
place calls and holds no provider credentials — see
[`docs/SECURITY.md`](../docs/SECURITY.md) at the repo root for why that's a
deliberate design choice, not a missing feature.

## Local development

```bash
cd web
npm install
npm run dev
```

Opens on `http://localhost:3000`. `npm run dev` (and `npm run build`) both
run `scripts/sync-data.mjs` first, which copies `../scenarios`, `../calls`,
and `../bug_report/BUGS.md` into `web/data/` (gitignored — regenerated on
every build). If you haven't placed any real calls yet, the dashboard still
renders with an "Empty" state for every scenario.

## Deploying to AWS (Amplify Hosting)

1. Push this repo to GitHub (already done if you're reading this from the
   deployed app).
2. In the [AWS Amplify Console](https://console.aws.amazon.com/amplify/),
   choose **Host a web app** → connect this GitHub repo → pick the branch.
3. Amplify should auto-detect [`amplify.yml`](../amplify.yml) at the repo
   root, which points it at the `web/` app root (monorepo mode). If it
   doesn't auto-detect, set the app root to `web` manually in the build
   settings.
4. **Before or right after the first deploy**, go to App settings → Access
   control and turn on basic-auth access control with a username/password
   of your choice. This gates the entire app at the CDN edge — do this
   before sharing the URL with anyone.
5. No environment variables need to be set. If the build settings UI shows
   an environment variables section, leave it empty — this app doesn't read
   any (see `docs/SECURITY.md`).
6. Deploy. Amplify rebuilds (and re-runs `sync-data.mjs`) on every push to
   the connected branch, so re-push after placing new calls to refresh the
   dashboard.

## What's intentionally not here

There's no "run a call" button. Triggering a real outbound call from a
public web page is a cost/abuse vector (see `docs/SECURITY.md`'s "If you
later add live-triggering" section) and needs proper per-user auth, rate
limiting, and a persistent backend — out of scope for this dashboard.
