from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mgsf.unity_agent_bridge import engine_adapters, probe_unity, run_unity_tests


@pytest.fixture
def unity_project(tmp_path: Path) -> Path:
    root = tmp_path / "Example"
    (root / "Assets").mkdir(parents=True)
    (root / "ProjectSettings").mkdir()
    (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
        "m_EditorVersion: 6000.3.0f1\n", encoding="utf-8"
    )
    return root


def test_registry_preserves_godot_entrypoint() -> None:
    adapters = engine_adapters()
    assert adapters[0] == {
        "engine": "godot", "adapter": "godot-capture",
        "entrypoint": "mgsf godot-capture", "stage": "active",
    }
    assert adapters[1]["stage"] == "incubation"


def test_read_only_probe_records_matching_ready_editor_but_holds(unity_project: Path, tmp_path: Path) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps({
            "success": True,
            "data": {"instances": [{"project": str(unity_project), "state": "ready"}]},
        }), "")

    result = probe_unity(unity_project, tmp_path / "evidence", runner=fake_run)
    evidence = json.loads(result.evidence_path.read_text())
    assert result.status == "HOLD"
    assert result.verdict == "READY"
    assert len(calls) == 1 and calls[0][0][1] == "status"
    assert calls[0][1]["check"] is False
    assert "shell" not in calls[0][1]
    assert "response" not in evidence["runner"]
    assert evidence["plugin_installed"] == "unverified"


def test_other_project_not_mistaken_as_ready(unity_project: Path, tmp_path: Path) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, json.dumps({
            "success": True, "data": {"instances": [
                {"project": str(tmp_path / "Other"), "state": "ready"},
            ]},
        }), "")
    assert probe_unity(unity_project, tmp_path, runner=fake_run).verdict == "UNAVAILABLE"


def test_dry_run_never_invokes_unity(unity_project: Path, tmp_path: Path) -> None:
    def forbid(*args, **kwargs):
        raise AssertionError("dry-run must not execute external commands")
    result = run_unity_tests(unity_project, tmp_path, runner=forbid)
    data = json.loads(result.evidence_path.read_text())
    assert result.status == "HOLD" and result.verdict == "NOT_RUN"
    assert data["planned_argv"][1] == "test"


def test_live_test_success_still_holds_promotion(unity_project: Path, tmp_path: Path) -> None:
    def fake_run(argv, **kwargs):
        Path(argv[argv.index("--output") + 1]).write_text(
            '<test-run total="2" passed="2" failed="0" skipped="0"/>',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(argv, 0, '{"success": true}', "")
    result = run_unity_tests(unity_project, tmp_path, execute=True, runner=fake_run)
    data = json.loads(result.evidence_path.read_text())
    assert result.verdict == "PASS" and result.status == "HOLD"
    assert data["nunit_counts"]["passed"] == 2
    assert len(data["report_sha256"]) == 64


@pytest.mark.parametrize("xml", [
    '<test-run total="2" passed="1" failed="1" skipped="0"/>',
    '<test-run total="0" passed="0" failed="0" skipped="0"/>',
    "<test-run",
    '<testsuite tests="2" failures="0"/>',
])
def test_invalid_or_failed_nunit_is_rejected(unity_project: Path, tmp_path: Path, xml: str) -> None:
    def fake_run(argv, **kwargs):
        Path(argv[argv.index("--output") + 1]).write_text(xml, encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")
    assert run_unity_tests(unity_project, tmp_path, execute=True, runner=fake_run).verdict == "FAIL"


def test_cli_failure_does_not_reuse_or_fabricate_results(unity_project: Path, tmp_path: Path) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 6, "", "license missing")
    result = run_unity_tests(unity_project, tmp_path, execute=True, runner=fake_run)
    assert result.verdict == "FAIL"
    data = json.loads(result.evidence_path.read_text())
    assert data["report_sha256"] is None
    assert data["runner"]["stderr_sha256"]


def test_missing_executable_records_unavailable(unity_project: Path, tmp_path: Path) -> None:
    def missing(*args, **kwargs):
        raise FileNotFoundError("unity")
    result = probe_unity(unity_project, tmp_path, runner=missing)
    assert result.verdict == "UNAVAILABLE"


def test_bad_projects_and_modes_fail_closed(tmp_path: Path, unity_project: Path) -> None:
    with pytest.raises(ValueError, match="requires Assets"):
        probe_unity(tmp_path / "not-unity", tmp_path)
    with pytest.raises(ValueError, match="mode must"):
        run_unity_tests(unity_project, tmp_path, mode="--delete-all")
    with pytest.raises(ValueError, match="positive"):
        probe_unity(unity_project, tmp_path, timeout_seconds=0)
