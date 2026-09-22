#!/usr/bin/env node
// Copies the non-secret, already-public repo content (scenario briefs, call
// transcripts/audio/metadata, the bug report) into web/data/ so it's part of
// the Next.js app's own build output — no filesystem access outside the app
// directory is needed at runtime, and no AWS credentials/S3 bucket are
// needed at all (see docs/SECURITY.md at the repo root). Re-run automatically
// as part of `npm run build` / `npm run dev`.
import { existsSync, mkdirSync, cpSync, copyFileSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = join(__dirname, "..");
const repoRoot = join(webRoot, "..");
const dataDir = join(webRoot, "data");

function copyDir(src, dest, label) {
  if (!existsSync(src)) {
    console.log(`[sync-data] skip ${label}: ${src} does not exist yet`);
    return;
  }
  cpSync(src, dest, { recursive: true });
  console.log(`[sync-data] copied ${label} -> ${dest}`);
}

rmSync(dataDir, { recursive: true, force: true });
mkdirSync(dataDir, { recursive: true });

copyDir(join(repoRoot, "scenarios"), join(dataDir, "scenarios"), "scenarios/");
copyDir(join(repoRoot, "calls"), join(dataDir, "calls"), "calls/");

const bugsSrc = join(repoRoot, "bug_report", "BUGS.md");
if (existsSync(bugsSrc)) {
  copyFileSync(bugsSrc, join(dataDir, "BUGS.md"));
  console.log("[sync-data] copied bug_report/BUGS.md");
} else {
  console.log("[sync-data] skip BUGS.md: not found");
}

console.log("[sync-data] done");
