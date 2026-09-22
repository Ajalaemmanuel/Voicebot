"""Timestamped, speaker-labeled transcript capture for a single call.

Fed by AgentSession conversation events in agent.py (finalized STT results
for the practice agent's side, finalized LLM/TTS turns for ours) so the
output can be cited as "transcript-07.txt at 1:23" in the bug report.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_SPEAKER_LABELS = {
    "caller": "Patient (our bot)",
    "agent": "Practice AI Agent",
}


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    return f"{minutes}:{secs:02d}"


@dataclass
class TranscriptTurn:
    speaker: str
    text: str
    timestamp_seconds: float

    def to_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = format_timestamp(self.timestamp_seconds)
        return data


class TranscriptWriter:
    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
        self.turns: list[TranscriptTurn] = []

    def add_turn(self, speaker: str, text: str, timestamp_seconds: float) -> None:
        if speaker not in _SPEAKER_LABELS:
            raise ValueError(
                f"Unknown speaker {speaker!r}; expected one of {sorted(_SPEAKER_LABELS)}"
            )
        self.turns.append(TranscriptTurn(speaker, text, timestamp_seconds))

    def to_text(self) -> str:
        lines = [f"Scenario: {self.scenario_name}"]
        for turn in self.turns:
            label = _SPEAKER_LABELS[turn.speaker]
            ts = format_timestamp(turn.timestamp_seconds)
            lines.append(f"[{ts}] {label}: {turn.text}")
        return "\n".join(lines) + "\n"

    def to_json(self) -> dict:
        return {
            "scenario": self.scenario_name,
            "turns": [turn.to_dict() for turn in self.turns],
        }

    def write(self, output_dir: Path) -> tuple[Path, Path]:
        output_dir = Path(output_dir)
        txt_path = output_dir / "transcript.txt"
        json_path = output_dir / "transcript.json"
        txt_path.write_text(self.to_text(), encoding="utf-8")
        json_path.write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")
        return txt_path, json_path
