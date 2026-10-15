"""Synthetic contract checks only. These never prove a skill improved a real game."""
import json
from pathlib import Path
import subprocess
import pytest

from mgsf.skill_ab_benchmark import prepare_skill_ab, run_skill_ab, _capture_check

PIN = "002d004c50b865406e58b3ec86508adab926d7f4"
BASELINE = "f0514229d7f2036ec25646d09e3647c8d870dadb"


def _inputs(tmp_path, *, phase="ROUTED", baseline=BASELINE):
    exp = {
        "schema_version": 1, "experiment_id": "gyro-puzzle-ab-001",
        "engine_version": "4.7.2", "baseline_commit": baseline,
        "task": "Implement grid puzzle undo and winning state.",
        "seed": 42, "test_script": "res://tests/ab_scenario.gd",
        "required_assertions": ["undo", "victory"],
    }
    route = {
        "schema_version": 1, "engine": "godot", "engine_version": "4.7.2",
        "status": phase, "evaluation_status": "HOLD",
        "selected_skill": "godot-genre-puzzle",
        "selected_url": "https://github.com/thedivergentai/Game-Dev-Agentic-Skills/blob/"
                        + PIN + "/skills/godot-genre-puzzle/SKILL.md",
        "provenance": {"source_commit": PIN},
    }
    a, b = tmp_path / "experiment-input.json", tmp_path / "route.json"
    a.write_text(json.dumps(exp), encoding="utf-8")
    b.write_text(json.dumps(route), encoding="utf-8")
    return a, b


def _plan(tmp_path):
    a, b = _inputs(tmp_path)
    return prepare_skill_ab(a, b, tmp_path / "planned") / "experiment.json"


def _git(*args):
    return subprocess.run(["git", *map(str, args)], capture_output=True, text=True, check=True).stdout.strip()


def _project(path):
    path.mkdir()
    _git("-C", path, "init", "-q")
    _git("-C", path, "config", "user.email", "test@example.com")
    _git("-C", path, "config", "user.name", "test")
    (path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    (path / "tests").mkdir()
    (path / "tests" / "ab_scenario.gd").write_text("extends SceneTree\n", encoding="utf-8")
    _git("-C", path, "add", ".")
    _git("-C", path, "commit", "-qm", "base")
    return _git("-C", path, "rev-parse", "HEAD")


def _projects(tmp_path):
    source = tmp_path / "source"
    baseline = _project(source)
    control, treatment = tmp_path / "control", tmp_path / "treatment"
    _git("clone", "-q", source, control)
    _git("clone", "-q", source, treatment)
    _git("-C", treatment, "config", "user.email", "test@example.com")
    _git("-C", treatment, "config", "user.name", "test")
    return control, treatment, baseline


def _fake_godot(path, *, missing_seed=False):
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "  print('4.7.2.stable.official.fake')\n"
        "else:\n"
        + ("" if missing_seed else "  print('MGSF_SEED:42')\n")
        + "  print('MGSF_ASSERT:undo:PASS')\n"
        + "  print('MGSF_ASSERT:victory:PASS')\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_plan_preserves_equal_spec_and_immutable_skill(tmp_path):
    a, b = _inputs(tmp_path)
    root = prepare_skill_ab(a, b, tmp_path / "out")
    control = (root / "control-PROMPT.md").read_text()
    treated = (root / "treatment-PROMPT.md").read_text()
    manifest = json.loads((root / "experiment.json").read_text())
    assert "Seed: 42" in control and "Seed: 42" in treated
    assert manifest["promotion_status"] == "HOLD"
    assert manifest["evidence_class"] == "experiment_plan_only"
    assert PIN in treated and PIN not in control
    assert manifest["skill"]["route_sha256"]


@pytest.mark.parametrize("change", [
    {"engine_version": "4.4.1"}, {"test_script": "res://../bad.gd"},
    {"required_assertions": ["undo", "undo"]}, {"seed": -1},
    {"baseline_commit": "abc"}, {"experiment_id": "../escape"},
])
def test_invalid_plan_fails_closed(tmp_path, change):
    a, b = _inputs(tmp_path)
    data = json.loads(a.read_text())
    data.update(change)
    a.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        prepare_skill_ab(a, b, tmp_path / "out")


def test_route_requires_unpromoted_immutable_source(tmp_path):
    a, b = _inputs(tmp_path, phase="HOLD")
    with pytest.raises(ValueError, match="ROUTED"):
        prepare_skill_ab(a, b, tmp_path / "out")
    data = json.loads(b.read_text())
    data["status"] = "ROUTED"
    data["selected_url"] = data["selected_url"].replace(PIN, "0" * 40)
    b.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="immutable"):
        prepare_skill_ab(a, b, tmp_path / "out")


def test_fake_engine_run_is_hold_without_direct_capture(tmp_path):
    control, treatment, baseline = _projects(tmp_path)
    a, b = _inputs(tmp_path, baseline=baseline)
    plan = prepare_skill_ab(a, b, tmp_path / "out") / "experiment.json"
    binary = tmp_path / "godot-fake"
    _fake_godot(binary)
    result = run_skill_ab(plan, control, treatment, binary, tmp_path / "runs")
    evidence = json.loads((result.root / "benchmark.json").read_text())
    assert result.status == "HOLD"
    assert result.verdict == "INSUFFICIENT_REAL_EVIDENCE"
    assert evidence["paired_pass_delta"] is None
    assert evidence["promotion_status"] == "HOLD"
    assert evidence["arms"]["control"]["passed_assertions"] == 2
    assert evidence["arms"]["treatment"]["passed_assertions"] == 2
    assert evidence["arms"]["control"]["stdout_sha256"]
    assert "--mgsf-seed=42" in evidence["arms"]["control"]["engine_command"]


def test_missing_seed_echo_prevents_comparison(tmp_path):
    control, treatment, baseline = _projects(tmp_path)
    a, b = _inputs(tmp_path, baseline=baseline)
    plan = prepare_skill_ab(a, b, tmp_path / "out") / "experiment.json"
    binary = tmp_path / "godot-fake"
    _fake_godot(binary, missing_seed=True)
    result = run_skill_ab(plan, control, treatment, binary, tmp_path / "runs")
    record = json.loads((result.root / "benchmark.json").read_text())
    assert result.status == "HOLD"
    assert "mismatched Godot seed echo" in record["arms"]["control"]["assertion_problems"][0]


def test_test_script_divergence_rejected(tmp_path):
    control, treatment, baseline = _projects(tmp_path)
    a, b = _inputs(tmp_path, baseline=baseline)
    plan = prepare_skill_ab(a, b, tmp_path / "out") / "experiment.json"
    (treatment / "tests/ab_scenario.gd").write_text("extends SceneTree\n# changed\n")
    _git("-C", treatment, "add", ".")
    _git("-C", treatment, "commit", "-qm", "test divergence")
    binary = tmp_path / "godot-fake"
    _fake_godot(binary)
    with pytest.raises(ValueError, match="byte-identical"):
        run_skill_ab(plan, control, treatment, binary, tmp_path / "runs")


def test_dirty_project_rejected(tmp_path):
    control, treatment, baseline = _projects(tmp_path)
    a, b = _inputs(tmp_path, baseline=baseline)
    plan = prepare_skill_ab(a, b, tmp_path / "out") / "experiment.json"
    (treatment / "junk.txt").write_text("uncommitted")
    binary = tmp_path / "godot-fake"
    _fake_godot(binary)
    with pytest.raises(ValueError, match="clean"):
        run_skill_ab(plan, control, treatment, binary, tmp_path / "runs")


def test_unrelated_baseline_rejected(tmp_path):
    control, treatment, _ = _projects(tmp_path)
    a, b = _inputs(tmp_path)
    plan = prepare_skill_ab(a, b, tmp_path / "out") / "experiment.json"
    binary = tmp_path / "godot-fake"
    _fake_godot(binary)
    with pytest.raises(ValueError, match="descend from pinned baseline"):
        run_skill_ab(plan, control, treatment, binary, tmp_path / "runs")


def test_capture_claim_cannot_replace_adapter_artifacts(tmp_path):
    assert _capture_check(None, "a" * 40)[0] is False
    sample = tmp_path / "adapter_eval.json"
    sample.write_text(json.dumps({
        "adapter": "godot-capture-adapter", "status": "PASS",
        "source_head_sha": "a" * 40, "criteria": {"x": True},
        "raw_capture_root": str(tmp_path / "nonexistent"),
    }))
    assert _capture_check(sample, "a" * 40)[0] is False


def test_arms_must_have_separate_worktrees(tmp_path):
    control, _, baseline = _projects(tmp_path)
    a, b = _inputs(tmp_path, baseline=baseline)
    plan = prepare_skill_ab(a, b, tmp_path / "out") / "experiment.json"
    binary = tmp_path / "godot-fake"
    _fake_godot(binary)
    with pytest.raises(ValueError, match="separate"):
        run_skill_ab(plan, control, control, binary, tmp_path / "runs")
