from pathlib import Path
import json
import subprocess

from mgsf.edenspark_agent_adapter import (
    REQUIRED_ACTIONS,
    build_agent_prompt,
    evaluate_result,
    load_mission,
    run_codex_iteration,
)
from mgsf.prototype_promotion import promote_prototype


def _mission(tmp_path: Path):
    path = tmp_path / "mission.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "mission_id": "neon-001",
        "title": "Test a one-button risk/reward loop",
        "hypothesis": "A single risky action is understandable and replayable.",
        "success_criteria": ["player can trigger the action", "feedback is visible"],
        "max_iterations": 3,
    }), encoding="utf-8")
    return path, load_mission(path)


def test_prompt_requires_engine_playtest_actions(tmp_path: Path) -> None:
    _, mission = _mission(tmp_path)
    prompt = build_agent_prompt(mission, 1)
    assert "Inspect the current scene" in prompt
    assert "Simulate meaningful keyboard/mouse input" in prompt
    assert "Capture at least one screenshot" in prompt
    assert "Read runtime/editor logs" in prompt


def test_live_evaluation_passes_only_with_runner_and_real_artifact(tmp_path: Path) -> None:
    _, mission = _mission(tmp_path)
    project = tmp_path / "project"
    artifact = project / ".mgsf/artifacts/neon-001/iteration-1/screenshot.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"not-a-real-png-but-a-real-recorded-file")
    result = {
        "mission_id": mission.mission_id,
        "iteration": 1,
        **{name: True for name in REQUIRED_ACTIONS},
        "runtime_errors": [],
        "observations": ["loop worked"],
        "changed_files": ["game/main.das"],
        "artifact_paths": [artifact.relative_to(project).as_posix()],
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    evaluation = evaluate_result(
        project,
        mission,
        result_path,
        tmp_path / "evidence",
        evidence_class="recorded_edenspark_agent_mcp_run",
        runner_record={"runner": "codex-exec", "returncode": 0},
    )
    assert evaluation.status == "PASS"
    assert evaluation.artifact_count == 1
    evidence = json.loads((evaluation.root / "evaluation.json").read_text(encoding="utf-8"))
    assert evidence["artifacts"][0]["sha256"]


def test_fixture_is_always_hold(tmp_path: Path) -> None:
    _, mission = _mission(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    result = {
        "mission_id": mission.mission_id,
        "iteration": 1,
        **{name: True for name in REQUIRED_ACTIONS},
        "runtime_errors": [],
        "observations": [],
        "changed_files": [],
        "artifact_paths": [],
    }
    result_path = tmp_path / "fixture-result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    evaluation = evaluate_result(
        project,
        mission,
        result_path,
        tmp_path / "evidence",
        evidence_class="deterministic_edenspark_fixture",
        runner_record=None,
    )
    assert evaluation.status == "HOLD"


def test_codex_runner_records_failed_structured_output(tmp_path: Path, monkeypatch) -> None:
    _, mission = _mission(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=7, stdout="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run)
    answer, runner = run_codex_iteration(project, mission, tmp_path / "evidence", iteration=1)
    data = json.loads(answer.read_text(encoding="utf-8"))
    assert runner["returncode"] == 7
    assert data["runtime_errors"]
    assert data["scene_inspected"] is False


def test_promotion_gate_holds_fixture_and_promotes_live_pass(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture" / "evaluation.json"
    fixture.parent.mkdir()
    fixture.write_text(json.dumps({
        "mission_id": "neon-001",
        "evidence_class": "deterministic_edenspark_fixture",
        "status": "HOLD",
        "score": 0.9,
    }), encoding="utf-8")
    hold = promote_prototype([fixture], tmp_path / "promotion-a")
    assert hold.status == "HOLD"

    live = tmp_path / "live" / "evaluation.json"
    live.parent.mkdir()
    live.write_text(json.dumps({
        "mission_id": "neon-001",
        "evidence_class": "recorded_edenspark_agent_mcp_run",
        "status": "PASS",
        "score": 1.0,
    }), encoding="utf-8")
    promote = promote_prototype([fixture, live], tmp_path / "promotion-b")
    assert promote.status == "PROMOTE"
    assert promote.selected_engine == "edenspark"


def test_live_evaluation_without_preserved_artifact_iterates(tmp_path: Path) -> None:
    _, mission = _mission(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    result = {
        "mission_id": mission.mission_id,
        "iteration": 1,
        **{name: True for name in REQUIRED_ACTIONS},
        "runtime_errors": [],
        "observations": ["agent claims screenshot, but no file was preserved"],
        "changed_files": ["game/main.das"],
        "artifact_paths": [],
    }
    result_path = tmp_path / "result-no-artifact.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    evaluation = evaluate_result(
        project,
        mission,
        result_path,
        tmp_path / "evidence",
        evidence_class="recorded_edenspark_agent_mcp_run",
        runner_record={"runner": "codex-exec", "returncode": 0},
    )
    assert evaluation.status == "ITERATE"
