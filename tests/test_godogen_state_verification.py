from __future__ import annotations

import json
from pathlib import Path

import pytest

from mgsf import godogen_state_verification as state
from mgsf.godogen_adapter import _sha


def setup_evidence(tmp_path: Path) -> tuple[Path, Path, dict]:
    project = tmp_path / "game"
    (project / "screenshots").mkdir(parents=True)
    mission = Path("fixtures/godogen/mission-gyro-live.json")
    samples = []
    x = 320.0
    for tick in range(15, 451, 15):
        action = ("right" if 30 <= tick <= 120 else
                  "left" if 180 <= tick <= 270 else "idle")
        if action == "right":
            x += 30
        elif action == "left":
            x -= 30
        samples.append({"tick": tick, "input": action, "state": {"x": x, "y": 180.0}})
    trace = {"schema_version": 1, "engine": "godot", "mission_id": "gyro-lab-state-001",
             "run_id": "local-test-001", "input_provenance": "godot_input_action_scripted",
             "samples": samples}
    (project / "screenshots/state-trace.json").write_text(json.dumps(trace), encoding="utf-8")
    (project / "screenshots/proof.mp4").write_bytes(b"mock-media-for-contract-tests")
    runner = {
        "runner": "mgsf-godot-runtime", "run_id": trace["run_id"],
        "returncode": 0, "trace_sha256": _sha(project / "screenshots/state-trace.json"),
        "video_sha256": _sha(project / "screenshots/proof.mp4"),
        "engine_checks": {
            name: {"returncode": 0} for name in (
                "dotnet_build", "godot_import", "godot_capture", "ffmpeg_encode"
            )
        },
    }
    return project, mission, runner


def test_state_contract_accepts_signed_tilt_windows() -> None:
    mission = state.load_contract("fixtures/godogen/mission-gyro-live.json")
    assert len(mission["state_checks"]) == 2
    assert mission["state_checks"][1]["max_delta"] < 0


def test_valid_mock_runtime_is_not_autonomous_proof(tmp_path: Path, monkeypatch) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    monkeypatch.setattr(state, "_verify_video", lambda *args: (True, {"duration_seconds": 15}))
    verdict = state.verify_state(
        project, mission, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", runner_record=runner,
        output_root=tmp_path / "evidence",
    )
    assert verdict.status == "PASS"
    assert verdict.autonomous_status == "HOLD"
    assert verdict.passed_checks == verdict.total_checks == 2
    evidence = json.loads((verdict.root / "state-evaluation.json").read_text())
    assert evidence["autonomous_status"] == "HOLD"
    assert evidence["state_trace"]["sha256"] == _sha(verdict.root / "state-trace.json")
    assert evidence["video"]["sha256"] == _sha(verdict.root / "proof.mp4")


def test_fixture_always_holds_despite_perfect_state(tmp_path: Path, monkeypatch) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    monkeypatch.setattr(state, "_verify_video", lambda *args: (True, {}))
    v = state.verify_state(
        project, mission, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", runner_record=runner,
        output_root=tmp_path / "evidence", fixture=True,
    )
    assert v.status == "HOLD"


def test_input_mismatch_cannot_pass(tmp_path: Path, monkeypatch) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    path = project / "screenshots/state-trace.json"
    data = json.loads(path.read_text())
    for sample in data["samples"]:
        if sample["input"] == "left":
            sample["input"] = "idle"
    path.write_text(json.dumps(data))
    runner["trace_sha256"] = _sha(path)
    monkeypatch.setattr(state, "_verify_video", lambda *args: (True, {}))
    v = state.verify_state(
        project, mission, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", runner_record=runner,
        output_root=tmp_path / "evidence",
    )
    assert v.status == "ITERATE"
    assert v.passed_checks == 1


def test_wrong_direction_blocks_pass(tmp_path: Path, monkeypatch) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    path = project / "screenshots/state-trace.json"
    data = json.loads(path.read_text())
    for s in data["samples"]:
        if s["tick"] in (180, 270):
            s["state"]["x"] = 0 if s["tick"] == 180 else 200
    path.write_text(json.dumps(data))
    runner["trace_sha256"] = _sha(path)
    monkeypatch.setattr(state, "_verify_video", lambda *args: (True, {}))
    v = state.verify_state(
        project, mission, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", runner_record=runner,
        output_root=tmp_path / "evidence",
    )
    assert v.status == "ITERATE"


def test_runner_hash_or_id_mismatch_holds(tmp_path: Path, monkeypatch) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    runner["run_id"] = "different-run"
    monkeypatch.setattr(state, "_verify_video", lambda *args: (True, {}))
    v = state.verify_state(
        project, mission, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", runner_record=runner,
        output_root=tmp_path / "evidence",
    )
    assert v.status == "HOLD"
    assert json.loads((v.root / "state-evaluation.json").read_text())["runner_verified"] is False


def test_video_probe_failure_iterates(tmp_path: Path, monkeypatch) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    monkeypatch.setattr(state, "_verify_video", lambda *args: (False, {}))
    v = state.verify_state(
        project, mission, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", runner_record=runner,
        output_root=tmp_path / "evidence",
    )
    assert v.status == "ITERATE"


def test_duplicate_ticks_refused(tmp_path: Path) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    trace = project / "screenshots/state-trace.json"
    data = json.loads(trace.read_text())
    data["samples"].insert(2, dict(data["samples"][1]))
    trace.write_text(json.dumps(data))
    with pytest.raises(state.StateVerificationError, match="ticks"):
        state.verify_state(
            project, mission, trace_path="screenshots/state-trace.json",
            video_path="screenshots/proof.mp4", runner_record=runner, output_root=tmp_path / "out",
        )


def test_path_escape_and_missing_proof_are_rejected(tmp_path: Path) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    with pytest.raises(state.StateVerificationError, match="inside"):
        state.verify_state(
            project, mission, trace_path="../secrets.json",
            video_path="screenshots/proof.mp4", runner_record=runner, output_root=tmp_path / "out",
        )
    (project / "screenshots/proof.mp4").unlink()
    with pytest.raises(state.StateVerificationError, match="absent"):
        state.verify_state(
            project, mission, trace_path="screenshots/state-trace.json",
            video_path="screenshots/proof.mp4", runner_record=runner, output_root=tmp_path / "out",
        )


def test_unmarked_project_cannot_run_any_commands(tmp_path: Path) -> None:
    project, mission, runner = setup_evidence(tmp_path)
    with pytest.raises(state.StateVerificationError, match="marked"):
        state.live_dogfood(project, mission, tmp_path / "evidence", godot="godot")


def test_invalid_contract_delta_rejected(tmp_path: Path) -> None:
    mission = state.load_contract("fixtures/godogen/mission-gyro-live.json")
    mission["state_checks"][0]["min_delta"] = -1
    bad = tmp_path / "bad-mission.json"
    bad.write_text(json.dumps(mission))
    with pytest.raises(state.StateVerificationError, match="sign"):
        state.load_contract(bad)
