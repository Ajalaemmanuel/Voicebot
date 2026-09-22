"""Load and validate scenario briefs used to drive the caller persona.

A scenario is a small YAML file describing who our "patient" caller is, what
they're trying to accomplish on the call, and (optionally) an explicit
edge-case instruction for the LLM to act on. See docs/DECISIONS.md #8 for why
this is a brief the LLM improvises from, rather than a fixed script.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ScenarioValidationError(ValueError):
    """Raised when a scenario file is missing required fields or references
    a patient_record file that doesn't exist."""


@dataclass
class Scenario:
    name: str
    slug: str
    persona: dict[str, Any]
    goal: str
    edge_case_instruction: str | None
    patient_record_path: Path | None
    max_turns: int | None
    source_path: Path

    def build_system_prompt(self) -> str:
        lines = [
            "You are a patient calling a medical practice on the phone. "
            "You are testing the practice's AI phone agent, but you must "
            "act like a genuine caller — do not reveal that you are an AI "
            "or that this is a test.",
            "",
            "Your identity:",
        ]
        for key, value in self.persona.items():
            label = key.replace("_", " ")
            lines.append(f"- {label}: {value}")

        lines += [
            "",
            f"Your goal for this call: {self.goal}",
        ]

        if self.edge_case_instruction:
            lines += [
                "",
                "Special instruction for this call (follow it naturally, in "
                "character, without announcing it):",
                self.edge_case_instruction.strip(),
            ]

        lines += [
            "",
            "Speak naturally and conversationally, the way a real patient "
            "would on the phone. Keep turns reasonably short. React to what "
            "the agent actually says rather than reciting a script.",
        ]
        return "\n".join(lines)


def _slugify(path: Path) -> str:
    return path.stem


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not raw.get("name"):
        raise ScenarioValidationError(f"{path}: missing required field 'name'")

    persona = raw.get("persona")
    if not isinstance(persona, dict) or not persona.get("name"):
        raise ScenarioValidationError(
            f"{path}: missing required field 'persona.name'"
        )

    goal = raw.get("goal")
    if not goal:
        raise ScenarioValidationError(f"{path}: missing required field 'goal'")

    patient_record_path = None
    patient_record = raw.get("patient_record")
    if patient_record:
        candidate = path.parent / patient_record
        if not candidate.is_file():
            raise ScenarioValidationError(
                f"{path}: patient_record file not found: {candidate}"
            )
        patient_record_path = candidate

    return Scenario(
        name=raw["name"],
        slug=_slugify(path),
        persona=persona,
        goal=goal,
        edge_case_instruction=raw.get("edge_case_instruction"),
        patient_record_path=patient_record_path,
        max_turns=raw.get("max_turns"),
        source_path=path,
    )
