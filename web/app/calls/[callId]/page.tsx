import { notFound } from "next/navigation";
import { getCall, listCalls } from "@/lib/data";

export function generateStaticParams() {
  return listCalls().map((c) => ({ callId: c.callId }));
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default async function CallPage({ params }: { params: Promise<{ callId: string }> }) {
  const { callId } = await params;
  const call = getCall(callId);
  if (!call) return notFound();

  return (
    <main>
      <a className="back-link" href="/">
        ← Back to scenarios
      </a>

      <section className="device">
        <div className="device-header">
          <span className="device-title">{call.scenarioSlug}</span>
          <span className={`status-dot ${call.outcome}`} />
        </div>

        <div className="meta-row">
          <span className="meta-pill">outcome: {call.outcome}</span>
          <span className="meta-pill">duration: {formatDuration(call.durationSeconds)}</span>
          {call.metadata?.stt && <span className="meta-pill">stt: {call.metadata.stt}</span>}
          {call.metadata?.llm && <span className="meta-pill">llm: {call.metadata.llm}</span>}
          {call.metadata?.tts && <span className="meta-pill">tts: {call.metadata.tts}</span>}
          {call.runResult?.error && <span className="meta-pill">error: {call.runResult.error}</span>}
        </div>

        {call.hasAudio ? (
          <div className="audio-bar">
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <audio controls src={`/audio/${call.callId}`} />
          </div>
        ) : (
          <div className="empty-state">No audio recording available for this call.</div>
        )}

        {call.transcript && call.transcript.turns.length > 0 ? (
          <div className="transcript">
            {call.transcript.turns.map((turn, i) => (
              <div className="turn" key={i}>
                <div className="turn-ts">{turn.timestamp}</div>
                <div className="turn-body">
                  <div className={`turn-speaker ${turn.speaker}`}>
                    {turn.speaker === "caller" ? "Patient (our bot)" : "Practice AI Agent"}
                  </div>
                  <div className="turn-text">{turn.text}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">No transcript available for this call.</div>
        )}
      </section>
    </main>
  );
}
