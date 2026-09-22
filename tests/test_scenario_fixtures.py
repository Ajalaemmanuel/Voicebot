"""Guards the actual checked-in scenario files (not just synthetic fixtures)
against schema drift — if one of these fails to load, a batch run would
silently skip or crash on that scenario."""
from pathlib import Path

from scenario_loader import load_scenario

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def test_at_least_ten_scenarios_exist():
    scenario_files = sorted(SCENARIOS_DIR.glob("*.yaml"))
    assert len(scenario_files) >= 10, "need at least 10 scenarios for the assignment minimum"


def test_every_scenario_file_loads_and_has_a_nonempty_prompt():
    scenario_files = sorted(SCENARIOS_DIR.glob("*.yaml"))
    assert scenario_files, "expected scenario YAML files under scenarios/"

    for path in scenario_files:
        scenario = load_scenario(path)
        prompt = scenario.build_system_prompt()
        assert scenario.persona.get("name"), f"{path} has no persona name"
        assert scenario.goal, f"{path} has no goal"
        assert len(prompt) > 50, f"{path} produced a suspiciously short prompt"


def test_scenario_slugs_are_unique():
    scenario_files = sorted(SCENARIOS_DIR.glob("*.yaml"))
    slugs = [load_scenario(path).slug for path in scenario_files]
    assert len(slugs) == len(set(slugs))
