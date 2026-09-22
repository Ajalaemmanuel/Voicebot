import json

import pytest

from agent import parse_job_metadata


def test_parses_scenario_path_and_call_id_from_json_metadata():
    raw = json.dumps({"scenario_path": "scenarios/cancel.yaml", "call_id": "cancel-ab12cd34"})

    scenario_path, call_id = parse_job_metadata(raw)

    assert scenario_path == "scenarios/cancel.yaml"
    assert call_id == "cancel-ab12cd34"


def test_falls_back_to_env_var_when_metadata_is_none(monkeypatch):
    monkeypatch.setenv("VOICEBOT_DEFAULT_SCENARIO", "scenarios/simple_scheduling_1.yaml")

    scenario_path, call_id = parse_job_metadata(None)

    assert scenario_path == "scenarios/simple_scheduling_1.yaml"
    assert call_id.startswith("console-")


def test_falls_back_to_env_var_when_metadata_is_not_valid_json(monkeypatch):
    monkeypatch.setenv("VOICEBOT_DEFAULT_SCENARIO", "scenarios/simple_scheduling_1.yaml")

    scenario_path, call_id = parse_job_metadata("not json")

    assert scenario_path == "scenarios/simple_scheduling_1.yaml"


def test_raises_when_no_metadata_and_no_fallback(monkeypatch):
    monkeypatch.delenv("VOICEBOT_DEFAULT_SCENARIO", raising=False)

    with pytest.raises(RuntimeError, match="metadata"):
        parse_job_metadata(None)


def test_raises_when_metadata_missing_call_id_and_no_fallback(monkeypatch):
    monkeypatch.delenv("VOICEBOT_DEFAULT_SCENARIO", raising=False)
    raw = json.dumps({"scenario_path": "scenarios/cancel.yaml"})

    with pytest.raises(RuntimeError, match="metadata"):
        parse_job_metadata(raw)
