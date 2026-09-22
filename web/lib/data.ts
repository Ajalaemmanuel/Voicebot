// Server-only data access. Everything here reads pre-copied, non-secret
// static content from ./data (populated by scripts/sync-data.mjs from the
// repo's scenarios/, calls/, and bug_report/ directories). No network calls,
// no environment variables, no credentials of any kind — see
// docs/SECURITY.md at the repo root for why that's a deliberate property of
// this dashboard, not an oversight.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import yaml from "js-yaml";

const DATA_DIR = join(process.cwd(), "data");
const SCENARIOS_DIR = join(DATA_DIR, "scenarios");
const CALLS_DIR = join(DATA_DIR, "calls");

export type ScenarioSummary = {
  slug: string;
  name: string;
  personaName: string;
  goal: string;
  hasEdgeCase: boolean;
  hasPatientRecord: boolean;
};

export type TranscriptTurn = {
  speaker: "caller" | "agent";
  text: string;
  timestamp_seconds: number;
  timestamp: string;
};

export type Transcript = {
  scenario: string;
  turns: TranscriptTurn[];
};

export type CallMetadata = {
  call_id?: string;
  scenario_file?: string;
  scenario_slug?: string;
  duration_seconds?: number;
  audio_file?: string;
  stt?: string;
  llm?: string;
  tts?: string;
};

export type RunResult = {
  room_name?: string;
  scenario_slug?: string;
  outcome?: "completed" | "no_answer" | "timeout" | "failed";
  duration_seconds?: number;
  error?: string | null;
};

export type CallSummary = {
  callId: string;
  scenarioSlug: string;
  outcome: RunResult["outcome"] | "unknown";
  durationSeconds: number | null;
  hasAudio: boolean;
  hasTranscript: boolean;
};

export type CallDetail = CallSummary & {
  transcript: Transcript | null;
  metadata: CallMetadata | null;
  runResult: RunResult | null;
  audioContentType: string | null;
};

function readJsonIfExists<T>(path: string): T | null {
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf-8")) as T;
}

export function listScenarios(): ScenarioSummary[] {
  if (!existsSync(SCENARIOS_DIR)) return [];

  return readdirSync(SCENARIOS_DIR)
    .filter((f) => f.endsWith(".yaml"))
    .map((file) => {
      const slug = file.replace(/\.yaml$/, "");
      const raw = yaml.load(readFileSync(join(SCENARIOS_DIR, file), "utf-8")) as any;
      return {
        slug,
        name: raw?.name ?? slug,
        personaName: raw?.persona?.name ?? "Unknown",
        goal: raw?.goal ?? "",
        hasEdgeCase: Boolean(raw?.edge_case_instruction),
        hasPatientRecord: Boolean(raw?.patient_record),
      };
    })
    .sort((a, b) => a.slug.localeCompare(b.slug));
}

function findAudioFile(callId: string): { path: string; contentType: string } | null {
  const oggPath = join(CALLS_DIR, callId, "audio.ogg");
  const mp3Path = join(CALLS_DIR, callId, "audio.mp3");
  if (existsSync(oggPath)) return { path: oggPath, contentType: "audio/ogg" };
  if (existsSync(mp3Path)) return { path: mp3Path, contentType: "audio/mpeg" };
  return null;
}

export function listCalls(): CallSummary[] {
  if (!existsSync(CALLS_DIR)) return [];

  return readdirSync(CALLS_DIR)
    .filter((entry) => statSync(join(CALLS_DIR, entry)).isDirectory())
    .map((callId) => summarizeCall(callId))
    .sort((a, b) => b.callId.localeCompare(a.callId));
}

function summarizeCall(callId: string): CallSummary {
  const dir = join(CALLS_DIR, callId);
  const metadata = readJsonIfExists<CallMetadata>(join(dir, "metadata.json"));
  const runResult = readJsonIfExists<RunResult>(join(dir, "run_result.json"));
  const audio = findAudioFile(callId);

  const scenarioSlug =
    metadata?.scenario_slug ?? runResult?.scenario_slug ?? callId.replace(/-[a-f0-9]{8}$/, "");

  return {
    callId,
    scenarioSlug,
    outcome: runResult?.outcome ?? (metadata ? "completed" : "unknown"),
    durationSeconds: metadata?.duration_seconds ?? runResult?.duration_seconds ?? null,
    hasAudio: audio !== null,
    hasTranscript: existsSync(join(dir, "transcript.json")),
  };
}

export function latestCallForScenario(slug: string): CallSummary | null {
  const calls = listCalls().filter((c) => c.scenarioSlug === slug);
  return calls[0] ?? null;
}

export function getCall(callId: string): CallDetail | null {
  const dir = join(CALLS_DIR, callId);
  if (!existsSync(dir)) return null;

  const summary = summarizeCall(callId);
  const transcript = readJsonIfExists<Transcript>(join(dir, "transcript.json"));
  const metadata = readJsonIfExists<CallMetadata>(join(dir, "metadata.json"));
  const runResult = readJsonIfExists<RunResult>(join(dir, "run_result.json"));
  const audio = findAudioFile(callId);

  return {
    ...summary,
    transcript,
    metadata,
    runResult,
    audioContentType: audio?.contentType ?? null,
  };
}

export function getAudioFile(callId: string): { path: string; contentType: string } | null {
  return findAudioFile(callId);
}

export function getBugsMarkdown(): string | null {
  const path = join(DATA_DIR, "BUGS.md");
  if (!existsSync(path)) return null;
  return readFileSync(path, "utf-8");
}
