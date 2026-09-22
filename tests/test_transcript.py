import json

import pytest

from transcript import TranscriptWriter, format_timestamp


def test_format_timestamp_under_a_minute():
    assert format_timestamp(7.4) == "0:07"


def test_format_timestamp_over_a_minute():
    assert format_timestamp(83.2) == "1:23"


def test_format_timestamp_rounds_down_to_whole_seconds():
    assert format_timestamp(59.9) == "0:59"


def test_add_turn_rejects_unknown_speaker():
    writer = TranscriptWriter(scenario_name="simple_scheduling_1")

    with pytest.raises(ValueError, match="speaker"):
        writer.add_turn("narrator", "hello", 0.0)


def test_to_text_orders_turns_and_labels_speakers():
    writer = TranscriptWriter(scenario_name="simple_scheduling_1")
    writer.add_turn("agent", "Thanks for calling Riverside Clinic, how can I help?", 0.0)
    writer.add_turn("caller", "Hi, I'd like to book a checkup.", 4.5)
    writer.add_turn("agent", "Sure, are you free Sunday at 10am?", 8.0)

    text = writer.to_text()
    lines = text.strip().splitlines()

    assert "simple_scheduling_1" in lines[0]
    assert lines[1].startswith("[0:00] Practice AI Agent:")
    assert lines[2].startswith("[0:04] Patient (our bot):")
    assert lines[3].startswith("[0:08] Practice AI Agent:")
    assert "Sunday at 10am" in lines[3]


def test_to_json_round_trips_turns():
    writer = TranscriptWriter(scenario_name="edge_weekend_request")
    writer.add_turn("caller", "Can I come in Sunday at 10am?", 83.0)

    data = writer.to_json()

    assert data["scenario"] == "edge_weekend_request"
    assert data["turns"] == [
        {"speaker": "caller", "text": "Can I come in Sunday at 10am?", "timestamp_seconds": 83.0, "timestamp": "1:23"}
    ]


def test_write_creates_txt_and_json_files(tmp_path):
    writer = TranscriptWriter(scenario_name="cancel")
    writer.add_turn("caller", "I need to cancel my appointment.", 1.0)
    writer.add_turn("agent", "Sure, what's your name?", 3.0)

    txt_path, json_path = writer.write(tmp_path)

    assert txt_path == tmp_path / "transcript.txt"
    assert json_path == tmp_path / "transcript.json"
    assert "cancel my appointment" in txt_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload["turns"]) == 2
