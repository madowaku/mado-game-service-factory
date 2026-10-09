from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mgsf.unity_cli_harness import run_unity_harness


def project(tmp_path: Path) -> Path:
    root = tmp_path / "game"
    (root / "ProjectSettings").mkdir(parents=True)
    (root / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3.0f1\n")
    (root / "Assets").mkdir()
    return root


def sample_result(root: Path) -> dict:
    return json.loads((root / "evaluation.json").read_text(encoding="utf-8"))


def fake_cli(project: Path, *, status_project: Path | None = None, tests: int = 2,
             failures: int = 0, status_success: bool = True, editor_ready: bool = True):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs["cwd"] == project
        assert kwargs["env"]["UNITY_PROJECT_PATH"] == str(project)
        if argv[1] == "version":
            data = {"success": True, "data": {"version": "1.0.0-beta.7"}}
        elif argv[1] == "status":
            instances = ([{"projectPath": str(status_project or project), "state": "ready"}]
                         if editor_ready else [])
            data = {"success": status_success, "data": {"editors": instances}}
        elif argv[1] == "list":
            data = {"success": True, "data": [{"name": "eval"}]}
        elif argv[1] == "test":
            out = Path(argv[argv.index("--output") + 1])
            out.write_text('<test-run total="%s" failed="%s" skipped="0"/>' % (tests, failures),
                           encoding="utf-8")
            data = {"success": True, "data": {"output": str(out)}}
            return subprocess.CompletedProcess(argv, 8 if failures else 0, json.dumps(data), "")
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(data), "")

    return run, calls


def test_fixture_never_runs_unity_or_passes(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"schema_version": 1, "steps": {
        "version": {"returncode": 0, "stdout": '{"success":true,"data":{}}'},
        "status": {"returncode": 0, "stdout": '{"success":true,"data":{}}'},
        "manifest": {"returncode": 0, "stdout": '{"success":true,"data":[]}'},
    }}), encoding="utf-8")

    def forbidden(*a, **kw):
        raise AssertionError("fixture mode must not call subprocess")

    monkeypatch.setattr(subprocess, "run", forbidden)
    result = run_unity_harness(root, tmp_path / "evidence", fixture=fixture, run_tests=True)
    data = sample_result(result.root)
    assert result.status == "HOLD"
    assert data["evidence_class"] == "deterministic_unity_fixture"
    assert all(item["origin"] == "deterministic_fixture" for item in data["steps"])
    assert not (result.root / "editmode-results.xml").exists()


def test_read_only_live_probe_holds_without_tests(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, calls = fake_cli(root)
    monkeypatch.setattr(subprocess, "run", runner)
    result = run_unity_harness(root, tmp_path / "evidence")
    assert result.status == "HOLD"
    assert [call[1] for call in calls] == ["version", "status", "list"]


def test_live_nunit_tests_pass_with_artifact_hash(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, calls = fake_cli(root, editor_ready=False)
    monkeypatch.setattr(subprocess, "run", runner)
    result = run_unity_harness(root, tmp_path / "evidence", run_tests=True)
    data = sample_result(result.root)
    assert result.status == "PASS"
    assert data["test_report"]["total"] == 2
    assert len(data["test_report"]["sha256"]) == 64
    assert [call[1] for call in calls] == ["version", "status", "test"]
    assert all(len(item["stdout_sha256"]) == 64 for item in data["steps"])


def test_other_editor_is_not_accepted(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, calls = fake_cli(root, status_project=tmp_path / "other")
    monkeypatch.setattr(subprocess, "run", runner)
    result = run_unity_harness(root, tmp_path / "evidence")
    assert result.status == "HOLD"
    assert [call[1] for call in calls] == ["version", "status"]


@pytest.mark.parametrize("tests,failures,expected", [(0, 0, "HOLD"), (4, 1, "ITERATE")])
def test_empty_and_failed_suites_never_pass(tmp_path: Path, monkeypatch, tests, failures, expected):
    root = project(tmp_path)
    runner, _ = fake_cli(root, tests=tests, failures=failures, editor_ready=False)
    monkeypatch.setattr(subprocess, "run", runner)
    result = run_unity_harness(root, tmp_path / "evidence", run_tests=True)
    assert result.status == expected


def test_unavailable_binary_holds_with_record(tmp_path: Path, monkeypatch):
    root = project(tmp_path)

    def missing(*args, **kwargs):
        raise FileNotFoundError("unity")

    monkeypatch.setattr(subprocess, "run", missing)
    result = run_unity_harness(root, tmp_path / "evidence", run_tests=True)
    assert result.status == "HOLD"
    assert sample_result(result.root)["steps"][0]["returncode"] == 127


def test_malformed_status_and_failed_envelope_hold(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, calls = fake_cli(root, status_success=False)
    monkeypatch.setattr(subprocess, "run", runner)
    result = run_unity_harness(root, tmp_path / "evidence")
    assert result.status == "HOLD"
    assert [call[1] for call in calls] == ["version", "status"]


def test_non_unity_project_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="not a Unity project"):
        run_unity_harness(tmp_path, tmp_path / "evidence")


def test_empty_pipeline_manifest_holds_even_when_cli_exits_zero(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, calls = fake_cli(root)

    def no_tools(argv, **kwargs):
        if argv[1] == "list":
            return subprocess.CompletedProcess(argv, 0, '{"success":true,"data":[]}', "")
        return runner(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", no_tools)
    result = run_unity_harness(root, tmp_path / "evidence")
    assert result.status == "HOLD"
    assert [call[1] for call in calls] == ["version", "status"]


def test_all_skipped_nunit_does_not_pass(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, calls = fake_cli(root, editor_ready=False)

    def skipped(argv, **kwargs):
        completed = runner(argv, **kwargs)
        if argv[1] == "test":
            report = Path(argv[argv.index("--output") + 1])
            report.write_text('<test-run total="2" passed="0" failed="0" skipped="2"/>',
                              encoding="utf-8")
        return completed

    monkeypatch.setattr(subprocess, "run", skipped)
    result = run_unity_harness(root, tmp_path / "evidence", run_tests=True)
    assert result.status == "HOLD"
    assert "nonempty NUnit report" in result.reason


def test_ready_editor_blocks_batch_test_to_avoid_project_lock(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, calls = fake_cli(root, editor_ready=True)
    monkeypatch.setattr(subprocess, "run", runner)
    result = run_unity_harness(root, tmp_path / "evidence", run_tests=True)
    assert result.status == "HOLD"
    assert "close the running Editor" in result.reason
    assert [call[1] for call in calls] == ["version", "status"]
    assert sample_result(result.root)["pipeline_verified"] is False


def test_batch_pass_does_not_claim_pipeline_verified(tmp_path: Path, monkeypatch):
    root = project(tmp_path)
    runner, _ = fake_cli(root, editor_ready=False)
    monkeypatch.setattr(subprocess, "run", runner)
    result = run_unity_harness(root, tmp_path / "evidence", run_tests=True)
    assert result.status == "PASS"
    data = sample_result(result.root)
    assert data["mode"] == "batch_editmode"
    assert data["pipeline_verified"] is False
