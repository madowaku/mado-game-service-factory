"""M0.9.2 synthetic integrity checks; real paired engine proof is CI-only."""
import json
from hashlib import sha256
from pathlib import Path
import subprocess

import pytest

from mgsf.skill_dogfood import (
    run_codex_dogfood_arm, evaluate_skill_dogfood,
)


BASELINE = "f0514229d7f2036ec25646d09e3647c8d870dadb"
PIN = "002d004c50b865406e58b3ec86508adab926d7f4"


def _sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _inputs(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    route = {
        "schema_version": 1,
        "status": "ROUTED",
        "selected_skill": "godot-testing-patterns",
        "selected_url": "https://github.com/thedivergentai/Game-Dev-Agentic-Skills/blob/" + PIN + "/skills/godot-testing-patterns/SKILL.md",
        "provenance": {"source_commit": PIN},
    }
    route_path = root / "route.json"
    route_path.write_text(json.dumps(route))
    plan = {
        "schema_version": 1,
        "experiment_id": "c6-ab-001",
        "evidence_class": "experiment_plan_only",
        "baseline_commit": BASELINE,
        "seed": 42,
        "engine_version": "4.7.2",
        "required_assertions": ["playfeel"],
        "skill": {
            "source_commit": PIN,
            "skill_id": "godot-testing-patterns",
            "skill_url": route["selected_url"],
            "route_sha256": _sha(route_path),
        },
    }
    plan_path = root / "experiment.json"
    plan_path.write_text(json.dumps(plan))
    (root / "control-PROMPT.md").write_text("Control task. No external skill.\n")
    (root / "treatment-PROMPT.md").write_text("Treatment task. Expert reference.\n")
    skill_path = root / "reviewed-SKILL.md"
    skill_path.write_text("Test best practices: review tests, do not execute scripts.\n")
    return plan_path, route_path, skill_path


def _runner(root: Path, arm: str, plan: Path, skill: Path | None = None, model="test-model", budget=900):
    folder = root / arm
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for label in ("prompt", "stdout", "stderr"):
        path = folder / (label + ".txt")
        path.write_text("recorded " + label)
        files[label + "_path"] = str(path.resolve())
        files[label + "_sha256"] = _sha(path)
    record = {
        "schema_version": 1,
        "runner": "mgsf-codex-skill-dogfood",
        "experiment_id": "c6-ab-001",
        "arm": arm,
        "model": model,
        "budget_seconds": budget,
        "initial_head": BASELINE,
        "returncode": 0,
        "command": ["codex", "exec", "--sandbox", "workspace-write", "--ask-for-approval", "never", "--model", model, "-"],
        "automatic_skill_install": False,
        "project_committed": False,
        "source_commit": PIN if skill else None,
        "reviewed_skill_path": str(skill.resolve()) if skill else None,
        "reviewed_skill_sha256": _sha(skill) if skill else None,
        **files,
    }
    receipt = folder / "runner.json"
    receipt.write_text(json.dumps(record))
    return receipt


def _benchmark(root: Path, plan: Path):
    bench = root / "benchmark.json"
    records = {}
    for arm, head in (("control", "a" * 40), ("treatment", "b" * 40)):
        folder = root / arm
        folder.mkdir(parents=True, exist_ok=True)
        stdout = folder / "stdout.log"
        stderr = folder / "stderr.log"
        stdout.write_text("MGSF_SEED:42\nMGSF_ASSERT:playfeel:PASS\n")
        stderr.write_text("")
        records[arm] = {
            "project_head": head, "capture_verified": True,
            "capture_problems": [], "assertion_problems": [],
            "engine_returncode": 0, "test_script_sha256": "c" * 64,
            "stdout_sha256": _sha(stdout), "stderr_sha256": _sha(stderr),
        }
        (folder / "run.json").write_text(json.dumps(records[arm]))
    b = {
        "schema_version": 1,
        "experiment_id": "c6-ab-001",
        "evidence_class": "paired_godot_runner_evidence",
        "status": "REVIEW",
        "promotion_status": "HOLD",
        "causal_claim_supported": False,
        "baseline_commit": BASELINE,
        "seed": 42,
        "required_assertions": ["playfeel"],
        "experiment_plan_sha256": _sha(plan),
        "paired_pass_delta": 0,
        "verdict": "TIED_ON_ASSERTIONS",
        "arms": records,
    }
    bench.write_text(json.dumps(b))
    return bench


def _suite(tmp_path):
    plan, route, skill = _inputs(tmp_path / "inputs")
    bench = _benchmark(tmp_path / "godot-evidence", plan)
    control = _runner(tmp_path / "receipts", "control", plan)
    treatment = _runner(tmp_path / "receipts", "treatment", plan, skill)
    return plan, route, skill, bench, control, treatment


def test_complete_synthetic_contract_is_review_never_promotion(tmp_path):
    plan, route, _, bench, control, treatment = _suite(tmp_path)
    result = evaluate_skill_dogfood(plan, route, bench, control, treatment, tmp_path / "out")
    assert result.status == "REVIEW"
    assert result.verdict == "TIED_ON_ASSERTIONS"
    payload = json.loads((result.root / "dogfood-evidence.json").read_text())
    assert payload["causal_claim_supported"] is False
    assert payload["promotion_status"] == "HOLD"


def test_identical_game_revisions_hold(tmp_path):
    plan, route, _, bench, control, treatment = _suite(tmp_path)
    raw = json.loads(bench.read_text())
    raw["arms"]["treatment"]["project_head"] = "a" * 40
    bench.write_text(json.dumps(raw))
    (bench.parent / "treatment" / "run.json").write_text(json.dumps(raw["arms"]["treatment"]))
    result = evaluate_skill_dogfood(plan, route, bench, control, treatment, tmp_path / "out")
    assert result.status == "HOLD"
    assert any("identical or unchanged" in issue for issue in result.blockers)


def test_missing_direct_capture_holds(tmp_path):
    plan, route, _, bench, control, treatment = _suite(tmp_path)
    raw = json.loads(bench.read_text())
    raw["arms"]["control"]["capture_verified"] = False
    bench.write_text(json.dumps(raw))
    (bench.parent / "control" / "run.json").write_text(json.dumps(raw["arms"]["control"]))
    assert evaluate_skill_dogfood(plan, route, bench, control, treatment, tmp_path / "out").status == "HOLD"


def test_changed_logged_stdout_blocks(tmp_path):
    plan, route, _, bench, control, treatment = _suite(tmp_path)
    (bench.parent / "control" / "stdout.log").write_text("tampered\n")
    result = evaluate_skill_dogfood(plan, route, bench, control, treatment, tmp_path / "out")
    assert any("integrity failure" in issue for issue in result.blockers)


@pytest.mark.parametrize("mutation", ["model", "budget", "skill", "runner"])
def test_codex_receipt_parity_and_integrity(tmp_path, mutation):
    plan, route, skill, bench, control, treatment = _suite(tmp_path)
    data = json.loads(treatment.read_text())
    if mutation == "model":
        data["model"] = "different-model"
    elif mutation == "budget":
        data["budget_seconds"] = 600
    elif mutation == "skill":
        skill.write_text("tampered content")
    else:
        data["returncode"] = 7
    treatment.write_text(json.dumps(data))
    result = evaluate_skill_dogfood(plan, route, bench, control, treatment, tmp_path / "out")
    assert result.status == "HOLD"


def test_plan_skill_source_mismatch_holds(tmp_path):
    plan, route, _, bench, control, treatment = _suite(tmp_path)
    data = json.loads(route.read_text())
    data["selected_skill"] = "godot-master"
    route.write_text(json.dumps(data))
    assert evaluate_skill_dogfood(plan, route, bench, control, treatment, tmp_path / "out").status == "HOLD"


def test_run_codex_rejects_missing_or_wrong_reviewed_skill(tmp_path, monkeypatch):
    plan, _, skill = _inputs(tmp_path / "inputs")
    project = tmp_path / "game"
    project.mkdir()
    (project / "project.godot").write_text("config_version=5\n")
    monkeypatch.setattr("mgsf.skill_dogfood._git_head", lambda _: BASELINE)
    with pytest.raises(ValueError, match="requires independently reviewed"):
        run_codex_dogfood_arm(plan, "treatment", project, tmp_path / "out", model="test-model")
    with pytest.raises(ValueError, match="digest mismatch"):
        run_codex_dogfood_arm(
            plan, "treatment", project, tmp_path / "out",
            model="test-model", reviewed_skill=skill, expected_skill_sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="control cannot"):
        run_codex_dogfood_arm(
            plan, "control", project, tmp_path / "out",
            model="test-model", reviewed_skill=skill,
        )


def test_run_codex_records_real_process_return_code_and_hashes(tmp_path, monkeypatch):
    plan, _, _ = _inputs(tmp_path / "inputs")
    project = tmp_path / "game"
    project.mkdir()
    (project / "project.godot").write_text("config_version=5\n")
    monkeypatch.setattr("mgsf.skill_dogfood._git_head", lambda _: BASELINE)
    def fake_run(*args, **kwargs):
        assert kwargs["cwd"] == project.resolve()
        assert args[0][0] == "codex"
        return subprocess.CompletedProcess(args[0], returncode=9, stdout="test-output", stderr="fail")
    monkeypatch.setattr("mgsf.skill_dogfood.subprocess.run", fake_run)
    path = run_codex_dogfood_arm(plan, "control", project, tmp_path / "out", model="test-model")
    record = json.loads(path.read_text())
    assert record["returncode"] == 9
    assert record["project_committed"] is False
    assert record["prompt_sha256"] == _sha(path.parent / "prompt.txt")
    assert record["stdout_sha256"] == _sha(path.parent / "codex.stdout.log")
