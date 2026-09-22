import pytest

from scenario_loader import Scenario, ScenarioValidationError, load_scenario

MINIMAL_YAML = """
name: Simple Scheduling
persona:
  name: Jamie Rivera
  date_of_birth: "1990-04-12"
  complaint: annual checkup
goal: Book a routine annual checkup appointment as soon as possible.
"""

FULL_YAML = """
name: Edge Case - Weekend Request
persona:
  name: Alex Chen
  date_of_birth: "1985-11-02"
  insurance: Blue Cross Blue Shield
  complaint: follow-up on knee pain
goal: Try to book a Sunday appointment.
edge_case_instruction: >
  Specifically ask for a Sunday at 10am appointment. If offered a weekday
  instead, push back once before accepting.
patient_record: patient_record.md
max_turns: 20
"""


def write_yaml(tmp_path, text, filename="scenario.yaml"):
    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")
    return path


def test_load_minimal_valid_scenario(tmp_path):
    path = write_yaml(tmp_path, MINIMAL_YAML)

    scenario = load_scenario(path)

    assert isinstance(scenario, Scenario)
    assert scenario.name == "Simple Scheduling"
    assert scenario.persona["name"] == "Jamie Rivera"
    assert scenario.goal.startswith("Book a routine")
    assert scenario.edge_case_instruction is None
    assert scenario.patient_record_path is None
    assert scenario.max_turns is None


def test_slug_is_derived_from_filename(tmp_path):
    path = write_yaml(tmp_path, MINIMAL_YAML, filename="simple_scheduling_1.yaml")

    scenario = load_scenario(path)

    assert scenario.slug == "simple_scheduling_1"


def test_load_full_scenario_with_patient_record(tmp_path):
    (tmp_path / "patient_record.md").write_text("# History\nSaw Dr. Lee in 2023.", encoding="utf-8")
    path = write_yaml(tmp_path, FULL_YAML, filename="edge_weekend_request.yaml")

    scenario = load_scenario(path)

    assert scenario.edge_case_instruction.strip().startswith("Specifically ask")
    assert scenario.patient_record_path == tmp_path / "patient_record.md"
    assert scenario.max_turns == 20


def test_missing_goal_raises(tmp_path):
    text = """
name: Broken
persona:
  name: Jamie Rivera
"""
    path = write_yaml(tmp_path, text)

    with pytest.raises(ScenarioValidationError, match="goal"):
        load_scenario(path)


def test_missing_persona_name_raises(tmp_path):
    text = """
name: Broken
persona:
  complaint: headache
goal: Do something
"""
    path = write_yaml(tmp_path, text)

    with pytest.raises(ScenarioValidationError, match="persona.name"):
        load_scenario(path)


def test_patient_record_missing_file_raises(tmp_path):
    text = """
name: Broken
persona:
  name: Jamie Rivera
goal: Do something
patient_record: does_not_exist.md
"""
    path = write_yaml(tmp_path, text)

    with pytest.raises(ScenarioValidationError, match="patient_record"):
        load_scenario(path)


def test_build_system_prompt_includes_persona_and_goal(tmp_path):
    path = write_yaml(tmp_path, MINIMAL_YAML)
    scenario = load_scenario(path)

    prompt = scenario.build_system_prompt()

    assert "Jamie Rivera" in prompt
    assert "annual checkup" in prompt
    assert "Book a routine annual checkup appointment as soon as possible." in prompt


def test_build_system_prompt_includes_edge_case_when_present(tmp_path):
    (tmp_path / "patient_record.md").write_text("history", encoding="utf-8")
    path = write_yaml(tmp_path, FULL_YAML)
    scenario = load_scenario(path)

    prompt = scenario.build_system_prompt()

    assert "Sunday at 10am" in prompt


def test_build_system_prompt_omits_edge_case_section_when_absent(tmp_path):
    path = write_yaml(tmp_path, MINIMAL_YAML)
    scenario = load_scenario(path)

    prompt = scenario.build_system_prompt()

    assert "edge case" not in prompt.lower()
