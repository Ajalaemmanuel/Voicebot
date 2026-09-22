const path = require("node:path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root explicitly — otherwise Next.js can mis-detect it
  // from an unrelated lockfile elsewhere on the machine/CI image.
  outputFileTracingRoot: path.join(__dirname),
  // This app reads only pre-copied, non-secret static content (scenarios,
  // call transcripts/audio, bug report) from ./data — see scripts/sync-data.mjs
  // and docs/SECURITY.md at the repo root. It never reads process.env for
  // any provider API key, and defines no NEXT_PUBLIC_* variables.
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
