from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from mgsf import godogen_qualification as q
from mgsf.godogen_adapter import GodogenEvaluation
from mgsf.godogen_generation_proof import AutonomyVerdict


MISSION = Path("fixtures/godogen/mission-gyro-live.json")


def checkout(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    for name, content in {
        "prompts/runtime.md": "Godot source",
        "engines/godot.md": "Godot guide",
        "LICENSE.md": "MIT",
        "asset-gen/SKILL.md": "asset skill",
    }.items():
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "remote", "add", "origin",
                    "https://github.com/htdt/godogen.git"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=MGSF",
                    "-c", "user.email=tests@example.org", "commit", "-qm", "pin"], check=True)
    sha = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                         text=True, capture_output=True, check=True).stdout.strip()
    return source, sha


def fake_tools(monkeypatch) -> None:
    monkeypatch.setattr(q.shutil, "which", lambda name: "/test/bin/" + name)


def test_real_qualification_preflight_never_stages_or_executes(
    tmp_path: Path, monkeypatch,
) -> None:
    source, sha = checkout(tmp_path)
    fake_tools(monkeypatch)
    target = tmp_path / "new-game"
    plan = q.preflight(source, target, MISSION, expected_sha=sha)
    assert plan["status"] == "READY"
    assert plan["live_codex_execution"] is False
    assert plan["live_godot_execution"] is False
    assert plan["upstream_sha"] == sha
    result = q.qualify(source, target, MISSION, expected_sha=sha,
                       output_root=tmp_path / "evidence")
    assert result.status == "READY"
    assert not target.exists()
    assert result.report is None


def test_missing_cli_is_blocked_not_simulated(tmp_path: Path, monkeypatch) -> None:
    source, sha = checkout(tmp_path)
    monkeypatch.setattr(q.shutil, "which", lambda tool: None if tool in {"godot", "codex"} else "/bin/" + tool)
    plan = q.preflight(source, tmp_path / "game", MISSION, expected_sha=sha)
    assert plan["status"] == "BLOCKED"
    assert plan["missing_tools"] == ["codex", "godot"]
    with pytest.raises(q.QualificationError, match="missing required tools"):
        q.qualify(source, tmp_path / "game", MISSION, expected_sha=sha,
                  output_root=tmp_path / "out", execute=True,
                  accept_generated_code_risk=True)
    assert not (tmp_path / "game").exists()


def test_double_consent_required_before_staging(tmp_path: Path, monkeypatch) -> None:
    source, sha = checkout(tmp_path)
    fake_tools(monkeypatch)
    game = tmp_path / "never-stage"
    with pytest.raises(q.QualificationError, match="accept-generated-code-risk"):
        q.qualify(source, game, MISSION, expected_sha=sha,
                  output_root=tmp_path / "out", execute=True)
    assert not game.exists()


def test_invalid_godogen_source_sha_refused(tmp_path: Path, monkeypatch) -> None:
    source, sha = checkout(tmp_path)
    fake_tools(monkeypatch)
    with pytest.raises(ValueError, match="pinned"):
        q.preflight(source, tmp_path / "game", MISSION, expected_sha="f" * 40)
    (source / "dirty").write_text("untrusted")
    with pytest.raises(ValueError, match="clean"):
        q.preflight(source, tmp_path / "game", MISSION, expected_sha=sha)


def test_refuse_evidence_inside_checkout_or_generated_game(tmp_path: Path, monkeypatch) -> None:
    source, sha = checkout(tmp_path)
    fake_tools(monkeypatch)
    game = tmp_path / "generated-game"
    with pytest.raises(q.QualificationError, match="outside"):
        q.qualify(source, game, MISSION, expected_sha=sha,
                  output_root=source / "evidence", execute=True,
                  accept_generated_code_risk=True)
    with pytest.raises(q.QualificationError, match="disjoint"):
        q.qualify(source, game, MISSION, expected_sha=sha,
                  output_root=game / "evidence", execute=True,
                  accept_generated_code_risk=True)
    assert not game.exists()


def test_real_run_contract_stops_on_no_codex_proof(tmp_path: Path, monkeypatch) -> None:
    source, sha = checkout(tmp_path)
    fake_tools(monkeypatch)
    game = tmp_path / "game"

    def no_generation(*a, **kw):
        root = Path(kw["output_root"]) if "output_root" in kw else Path(a[2])
        folder = root / "gyro-lab-state-001" / "iteration-1"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "evaluation.json").write_text('{"status":"HOLD"}')
        return GodogenEvaluation(folder, "HOLD", "Codex unavailable", 0)

    monkeypatch.setattr(q, "run_godogen_loop", no_generation)
    monkeypatch.setattr(q, "capture_generated_game", lambda *a, **k:
                        pytest.fail("no replay should start without successful Codex generation"))
    verdict = q.qualify(source, game, MISSION, expected_sha=sha,
                        output_root=tmp_path / "evidence",
                        execute=True, accept_generated_code_risk=True)
    assert verdict.status == "HOLD"
    assert verdict.stage == "codex-generation"
    assert game.exists()
    data = json.loads(verdict.report.read_text())
    assert data["real_codex_observed"] is False
    assert data["autonomous_generation_qualified"] is False


def test_stage_failure_is_logged_as_hold_never_pass(tmp_path: Path, monkeypatch) -> None:
    source, sha = checkout(tmp_path)
    fake_tools(monkeypatch)
    def reject_run(*args, **kwargs):
        raise RuntimeError("SECRET_SHOULD_NOT_BE_PERSISTED")
    monkeypatch.setattr(q, "run_godogen_loop", reject_run)
    result = q.qualify(source, tmp_path / "game", MISSION, expected_sha=sha,
                       output_root=tmp_path / "evidence", execute=True,
                       accept_generated_code_risk=True)
    assert result.status == "HOLD"
    assert result.report.is_file()
    data = json.loads(result.report.read_text())
    assert data["failed_stage"] == "codex-generation"
    assert data["codex_stage_attempted"] is True
    assert "SECRET_SHOULD_NOT_BE_PERSISTED" not in json.dumps(data)
    assert not data["autonomous_generation_qualified"]


def test_synthetic_positive_contract_not_claimed_as_real_engine(tmp_path: Path, monkeypatch) -> None:
    """All external calls replaced with fakes, only orchestrator wiring is tested."""
    source, sha = checkout(tmp_path)
    fake_tools(monkeypatch)
    root = tmp_path / "evidence"
    game = tmp_path / "game"

    def mocked_agent(project, mission, evidence_root, **kwargs):
        folder = Path(evidence_root) / "gyro-lab-state-001/iteration-1"
        (folder / "runner").mkdir(parents=True)
        (folder / "evaluation.json").write_text('{"status":"PASS"}')
        (folder / "runner/runner.json").write_text(
            '{"runner":"codex-exec","returncode":0}')
        return GodogenEvaluation(folder, "PASS", "mock agent", 1)

    def mocked_capture(project, mission, evidence_root, **kwargs):
        proof_dir = Path(evidence_root) / "gyro-lab-state-001/mock-test"
        proof_dir.mkdir(parents=True)
        proof = proof_dir / "frame-proof.json"
        proof.write_text('{"status":"PASS"}')
        (proof_dir / "state-evaluation.json").write_text('{"status":"PASS"}')
        return proof

    def mocked_gate(project, mission, frame_proof, state_evidence,
                    godogen_evaluation, codex_runner, output_root, **kwargs):
        out = Path(output_root) / "gyro-lab-state-001/mock-test"
        out.mkdir(parents=True)
        (out / "autonomy-evaluation.json").write_text('{"status":"PASS"}')
        return AutonomyVerdict(out, "PASS", 11, 11)

    monkeypatch.setattr(q, "run_godogen_loop", mocked_agent)
    monkeypatch.setattr(q, "capture_generated_game", mocked_capture)
    monkeypatch.setattr(q, "verify_autonomous_generation", mocked_gate)
    result = q.qualify(source, game, MISSION, expected_sha=sha,
                       output_root=root, execute=True, accept_generated_code_risk=True)
    assert result.status == "PASS"  # mocked contract only; NEVER recorded as live dogfood
    data = json.loads(result.report.read_text())
    assert data["stage"] == "autonomy-gate"
    assert data["codex_stage_attempted"] is True
    assert data["real_codex_observed"] is True
    assert data["independent_game_replay_observed"] is True
    assert data["artifacts"]["autonomy_evaluation"].endswith("autonomy-evaluation.json")
