from __future__ import annotations

import json
from pathlib import Path

import pytest

from mgsf import godogen_frame_proof as proof
from mgsf import godogen_generation_proof as generation
from mgsf.godogen_adapter import _sha
from mgsf.godogen_source_fingerprint import fingerprint_project, SourceFingerprintError
from mgsf.godogen_state_verification import StateVerificationError


MISSION = Path("fixtures/godogen/mission-gyro-live.json")


def write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def evidence(tmp_path: Path):
    project = tmp_path / "game"
    project.mkdir()
    video = project / "screenshots/proof.mp4"
    video.parent.mkdir()
    video.write_bytes(b"mock video for isolated unit test")
    trace = write_json(project / "screenshots/state-trace.json", {
        "schema_version": 1, "engine": "godot",
        "mission_id": "gyro-lab-state-001", "run_id": "local-frame-001",
        "samples": [
            {"tick": tick, "input": ("right" if 30 <= tick <= 120 else
                                      "left" if 180 <= tick <= 270 else "idle"),
             "state": {"x": (320 + 2 * max(0, min(tick, 120) - 29)
                              - 2 * max(0, min(tick, 270) - 179)), "y": 180}}
            for tick in range(15, 421, 15)
        ],
    })
    runner = {"runner": "mgsf-godot-runtime", "run_id": "local-frame-001",
              "returncode": 0, "trace_sha256": _sha(trace),
              "video_sha256": _sha(video), "source": "hand-authored-test"}
    state = write_json(tmp_path / "state/state-evaluation.json", {
        "service": "godogen-gameplay-state-verification",
        "mission_id": "gyro-lab-state-001", "run_id": "local-frame-001",
        "status": "PASS", "runner_verified": True, "video_verified": True,
        "checks": [{"pass": True}, {"pass": True}, {"pass": True}],
        "state_trace": {"sha256": _sha(trace)},
        "video": {"sha256": _sha(video)},
        "runner": runner,
    })
    return project, trace, video, state


def fake_frame(x: int, y: int = 180, width: int = 640, height: int = 360, color=(38, 212, 186)) -> bytes:
    b = bytearray(width * height * 3)
    for py in range(y - 15, y + 15):
        for px in range(x - 15, x + 15):
            off = (py * width + px) * 3
            b[off:off+3] = bytes(color)
    return bytes(b)


def setup_decoder(monkeypatch, project: Path, *, shifted: int = 0, blank: bool = False) -> None:
    trace = json.loads((project / "screenshots/state-trace.json").read_text())
    ticks = {row["tick"]: row["state"]["x"] for row in trace["samples"]}
    monkeypatch.setattr(proof, "_verify_video", lambda *args: (
        True, {"duration_seconds": 15.0, "streams": [
            {"codec_type": "video", "width": 640, "height": 360}]}))
    monkeypatch.setattr(proof, "_decode_rgb", lambda _exe, _video, tick, _fps, _w, _h: (
        bytes(640 * 360 * 3) if blank else fake_frame(round(ticks[tick]) + shifted)))


def run_frame(tmp_path, project, state):
    return proof.verify_frame_proof(
        project, MISSION, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", state_evidence_path=state,
        output_root=tmp_path / "frame-evidence",
    )


def test_color_centroid_scans_actual_frame_not_declared_center() -> None:
    centroid = proof.rgb_centroid(fake_frame(150), 640, 360, (38, 212, 186), 20, 500, 2900)
    assert centroid is not None
    assert abs(centroid[0] - 150) <= 1
    assert abs(centroid[1] - 180) <= 1
    assert centroid[2] == 900
    assert proof.rgb_centroid(bytes(640*360*3), 640, 360, (38,212,186), 20, 500, 2900) is None


def test_mocked_independent_pixels_correspond_to_state(tmp_path: Path, monkeypatch) -> None:
    project, trace, video, state = evidence(tmp_path)
    setup_decoder(monkeypatch, project)
    result = run_frame(tmp_path, project, state)
    assert (result.status, result.matched, result.total) == ("PASS", 5, 5)
    data = json.loads((result.root / "frame-proof.json").read_text())
    assert data["autonomous_status"] == "HOLD"
    assert data["source_trace_sha256"] == _sha(trace)
    assert data["source_video_sha256"] == _sha(video)


def test_forged_or_static_visual_fails_alignment(tmp_path: Path, monkeypatch) -> None:
    project, _, _, state = evidence(tmp_path)
    setup_decoder(monkeypatch, project, shifted=32)
    result = run_frame(tmp_path, project, state)
    assert result.status == "ITERATE"
    assert result.matched == 0


def test_missing_colored_player_fails(tmp_path: Path, monkeypatch) -> None:
    project, _, _, state = evidence(tmp_path)
    setup_decoder(monkeypatch, project, blank=True)
    result = run_frame(tmp_path, project, state)
    assert result.status == "ITERATE"
    assert result.matched == 0


def test_corrupted_state_hash_holds_even_with_matching_pixels(tmp_path: Path, monkeypatch) -> None:
    project, trace, _, state = evidence(tmp_path)
    setup_decoder(monkeypatch, project)
    info = json.loads(state.read_text())
    info["state_trace"]["sha256"] = "0" * 64
    write_json(state, info)
    result = run_frame(tmp_path, project, state)
    assert result.status == "HOLD"


def test_frame_fixture_never_promotes(tmp_path: Path, monkeypatch) -> None:
    project, _, _, state = evidence(tmp_path)
    setup_decoder(monkeypatch, project)
    result = proof.verify_frame_proof(
        project, MISSION, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", state_evidence_path=state,
        output_root=tmp_path / "frame", fixture=True,
    )
    assert result.status == "HOLD"


def test_invalid_probe_rejected(tmp_path: Path) -> None:
    mission = json.loads(MISSION.read_text())
    mission["frame_probe"]["ticks"] = [60, 60, 210]
    path = write_json(tmp_path / "mission.json", mission)
    with pytest.raises(StateVerificationError, match="ticks"):
        proof.load_frame_probe(json.loads(path.read_text()))


def test_generated_capture_refuses_fixture_before_engine(tmp_path: Path) -> None:
    project, *_ = evidence(tmp_path)
    (project / ".mgsf-gyro-dogfood").write_text("mgsf-gyro-state-dogfood-v1")
    with pytest.raises(StateVerificationError, match="hand-authored"):
        generation.capture_generated_game(project, MISSION, tmp_path / "out", godot="godot")


def test_source_fingerprint_rejects_missing_scene_and_symlink(tmp_path: Path) -> None:
    project = tmp_path / "src"
    project.mkdir()
    (project / "project.godot").write_text("config_version=5")
    (project / "game.csproj").write_text("<Project/>")
    (project / "Game.cs").write_text("public partial class Game {}")
    with pytest.raises(SourceFingerprintError, match="scene"):
        fingerprint_project(project)
    (project / "game.tscn").write_text("[gd_scene]")
    assert len(fingerprint_project(project)["digest"]) == 64
    (project / "outside.cs").symlink_to(project / "Game.cs")
    with pytest.raises(SourceFingerprintError, match="linked"):
        fingerprint_project(project)


def test_autonomy_fixture_holds_missing_provenance(tmp_path: Path, monkeypatch) -> None:
    project, _, _, state = evidence(tmp_path)
    setup_decoder(monkeypatch, project)
    result = run_frame(tmp_path, project, state)
    generated = write_json(tmp_path / "godogen/evaluation.json", {})
    runner = write_json(tmp_path / "codex/runner.json", {})
    verdict = generation.verify_autonomous_generation(
        project, MISSION,
        frame_proof=result.root / "frame-proof.json", state_evidence=state,
        godogen_evaluation=generated, codex_runner=runner,
        output_root=tmp_path / "autonomy", fixture=True,
    )
    assert verdict.status == "HOLD"
    data = json.loads((verdict.root / "autonomy-evaluation.json").read_text())
    assert data["checks"]["pinned_godogen_intake"] is False
    assert data["checks"]["codex_runner_recorded"] is False


def test_bogus_codex_runner_never_promotes(tmp_path: Path, monkeypatch) -> None:
    project, _, _, state = evidence(tmp_path)
    setup_decoder(monkeypatch, project)
    frame = run_frame(tmp_path, project, state)
    generated = write_json(tmp_path / "codex/evaluation.json", {"status": "PASS"})
    runner = write_json(tmp_path / "codex/runner.json",
                        {"runner": "codex-exec", "returncode": 0, "cwd": str(project)})
    verdict = generation.verify_autonomous_generation(
        project, MISSION, frame_proof=frame.root / "frame-proof.json",
        state_evidence=state, godogen_evaluation=generated,
        codex_runner=runner, output_root=tmp_path / "auto",
    )
    assert verdict.status == "HOLD"
