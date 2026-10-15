import json
from pathlib import Path

import pytest

from mgsf.agent_skill_router import load_skill_registry, run_skill_route


REGISTRY = Path("catalog/agent-skills.yaml")
FIXTURE = Path("fixtures/agent-skills/gyro-lab-puzzle.json")


def _request(tmp_path: Path, **overrides: object) -> Path:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw.update(overrides)
    path = tmp_path / "mission.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _run(tmp_path: Path, **overrides: object) -> dict:
    request = _request(tmp_path, **overrides)
    result = run_skill_route(request, REGISTRY, tmp_path / "evidence")
    output = json.loads((result.root / "skill-route.json").read_text(encoding="utf-8"))
    assert (result.root / "CODEX_TASK.md").is_file()
    assert output["evaluation_status"] == "HOLD"
    assert output["provenance"]["scripts_executed"] is False
    assert output["provenance"]["upstream_file_content_verified"] is False
    return output


def test_registry_and_puzzle_selection(tmp_path: Path) -> None:
    assert len(load_skill_registry(REGISTRY)["skills"]) >= 10
    record = _run(tmp_path)
    assert record["status"] == "ROUTED"
    assert record["selected_skill"] == "godot-genre-puzzle"
    assert "002d004c50b865406e58b3ec86508adab926d7f4" in record["selected_url"]
    assert "genre:puzzle" in record["match_signals"]


def test_master_fallback_when_no_specialized_match(tmp_path: Path) -> None:
    record = _run(tmp_path, genre="general", task="General level loading.", capabilities=[])
    assert record["selected_skill"] == "godot-master"
    assert record["match_score"] == 0


def test_visual_qa_and_balancing(tmp_path: Path) -> None:
    record = _run(tmp_path, genre="general", phase="playtest", capabilities=["screenshot", "visual"])
    assert record["selected_skill"] == "godot-agent-vision"
    record = _run(tmp_path, genre="general", phase="verify", capabilities=["balance", "economy"])
    assert record["selected_skill"] == "godot-monte-carlo-balancer"


def test_time_trial_and_deterministic_tie_break(tmp_path: Path) -> None:
    record = _run(tmp_path, genre="general", capabilities=["ghost", "time-trial"])
    assert record["selected_skill"] == "godot-game-loop-time-trial"
    record = _run(tmp_path, genre="general", phase="verify", task="Misc", capabilities=["test", "visual"])
    assert record["selected_skill"] == "godot-agent-vision"  # sorted by skill id


def test_older_engine_is_hold_even_for_matching_skill(tmp_path: Path) -> None:
    record = _run(tmp_path, engine_version="4.4.1")
    assert record["status"] == "HOLD"
    assert record["selected_skill"] is None
    assert "migration" in record["reason"]


def test_migration_explicit_only(tmp_path: Path) -> None:
    record = _run(tmp_path, phase="migration", capabilities=[])
    assert record["selected_skill"] == "godot-version-migration"


@pytest.mark.parametrize("overrides", [
    {"mission_id": "../escape"}, {"engine": "bevy"},
    {"engine_version": "stable"}, {"phase": "launch"},
    {"capabilities": ["../skill"]}, {"capabilities": ["grid", "grid"]},
])
def test_bad_request_fails_closed(tmp_path: Path, overrides: dict) -> None:
    with pytest.raises(ValueError):
        _run(tmp_path, **overrides)


def test_bad_registry_path_and_duplicate_skill_fails_closed(tmp_path: Path) -> None:
    import yaml
    data = load_skill_registry(REGISTRY)
    data["skills"][0]["path"] = "../foo"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid skill path"):
        load_skill_registry(bad)
    data["skills"][0]["path"] = "skills/godot-master/SKILL.md"
    data["skills"].append(dict(data["skills"][0]))
    bad.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate skill id"):
        load_skill_registry(bad)


def test_deterministic_evidence_bytes(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = run_skill_route(request, REGISTRY, tmp_path / "evidence")
    before = (first.root / "skill-route.json").read_bytes()
    second = run_skill_route(request, REGISTRY, tmp_path / "evidence")
    assert (second.root / "skill-route.json").read_bytes() == before
