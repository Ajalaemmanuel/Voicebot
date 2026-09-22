// Streams a call's own recording from the bundled ./data/calls directory.
// Deliberately reads only that one pre-copied file by a validated callId —
// no arbitrary path is ever accepted from the request, and this route
// touches no secret/credential of any kind (see docs/SECURITY.md).
import { readFileSync } from "node:fs";
import { NextRequest, NextResponse } from "next/server";
import { getAudioFile, listCalls } from "@/lib/data";

const VALID_CALL_IDS = new Set(listCalls().map((c) => c.callId));

export async function GET(_req: NextRequest, { params }: { params: Promise<{ callId: string }> }) {
  const { callId } = await params;

  if (!VALID_CALL_IDS.has(callId)) {
    return new NextResponse("Not found", { status: 404 });
  }

  const audio = getAudioFile(callId);
  if (!audio) {
    return new NextResponse("Not found", { status: 404 });
  }

  const bytes = readFileSync(audio.path);
  return new NextResponse(bytes, {
    headers: {
      "Content-Type": audio.contentType,
      "Cache-Control": "private, max-age=3600",
    },
  });
}
