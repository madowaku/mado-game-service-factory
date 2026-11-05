from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import struct

import pytest

from mgsf.studio_pipeline import (
    DIRECT_CAPTURE_CHECKS,
    build_pipeline_pack,
    create_pipeline_pack,
    evaluate_godot_pipeline,
)
from mgsf.studio_orchestrator import load_studio_mission


SHA = "f0514229d7f2036ec25646d09e3647c8d870dadb"


def _mission(tmp_path: Path, *, engine: str = "godot", tracks=None) -> Path:
    target = tmp_path / "mission.json"
    target.write_text(json.dumps({
        "schema_version": 1,
        "mission_id": "slice-smoke-001",
        "title": "Direct capture smoke",
        "hypothesis": "One interaction plays visibly",
        "engine": engine,
        "workstreams": tracks or ["gameplay"],
        "success_criteria": ["Play the scene", "Capture direct gameplay PNG"],
    }), encoding="utf-8")
    return target


def _file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _fake_png() -> bytes:
    # Unit fixture: header only. Not a real rendered screenshot!
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 1280, 720)


def _adapter(tmp_path: Path, *, sha=SHA) -> tuple[Path, Path]:
    project = tmp_path / "game"
    _file(project / "project.godot", b"[application]\n")
    parent = tmp_path / "evidence" / "godot-capture-adapter" / "vertical-slice-c6-direct"
    raw = parent / "raw-capture"
    _file(parent / "godot-preflight.log", b"preflight OK\n")
    _file(parent / "godot-runtime.log", b"direct game run OK\n")
    _file(raw / "capture.json", json.dumps({
        "source": {"evidence_class": "recorded_gameplay_capture", "source_head_sha": sha},
    }).encode())
    _file(raw / "timeline.jsonl", b'{"event":"input"}\n')
    _file(raw / "before-swing.png", _fake_png())
    _file(raw / "reveal.png", _fake_png())
    payload = {
        "adapter": "godot-capture-adapter",
        "status": "PASS",
        "project": str(project.resolve()),
        "raw_capture_root": str(raw.resolve()),
        "source_head_sha": sha,
        "criteria": {key: True for key in DIRECT_CAPTURE_CHECKS},
    }
    evaluation = _file(parent / "adapter_eval.json", json.dumps(payload).encode())
    return project, evaluation


def _result(tmp_path, project, mission, evaluation, *, source_sha=SHA):
    path = evaluate_godot_pipeline(project, mission, evaluation, tmp_path / "output", expected_source_sha=source_sha)
    return json.loads(path.read_text(encoding="utf-8"))


def test_pack_contains_real_cockpit_cli_contract_and_no_execution(tmp_path: Path) -> None:
    mission = _mission(tmp_path, tracks=["gameplay", "art", "audio"])
    pack = create_pipeline_pack(mission, tmp_path / "packs")
    content = json.loads(pack.read_text(encoding="utf-8"))
    steps = {x["step"]: x["argv"] for x in content["cockpit"]["commands"]}
    assert steps["mission_create"][:3] == ["mado-cockpit", "mission", "create"]
    assert steps["operator_start"][:3] == ["mado-cockpit", "operator", "start"]
    assert "--require" in steps["operator_start"]
    assert "session_trace" in steps["operator_start"]
    assert steps["builder_launch"][-1] == "builder"
    assert steps["qa_launch"][-1] == "qa"
    assert "qa_report=<QA_WORKTREE_RELATIVE_FILE>" in steps["qa_result"]
    assert "git_diff=<WORKTREE_RELATIVE_FILE>" not in steps["builder_result"]
    assert content["agent_execution_performed"] is False
    assert content["promotion_eligible"] is False
    assert content["creative_adapters"]["art"]["requested"]
    assert content["creative_adapters"]["audio"]["requested"]
    assert "ART:" in (pack.parent / "builder-prompt.md").read_text()
    assert "AUDIO:" in (pack.parent / "builder-prompt.md").read_text()
    assert "independent QA" in (pack.parent / "qa-prompt.md").read_text()


def test_godot_capture_recipe_is_advisory(tmp_path: Path) -> None:
    content = build_pipeline_pack(load_studio_mission(_mission(tmp_path)))
    assert content["godot_capture"]["supported"] is True
    assert content["godot_capture"]["command_template"][:2] == ["mgsf", "godot-capture"]


def test_edenspark_cannot_be_mislabeled_as_godot_verified(tmp_path: Path) -> None:
    mission = _mission(tmp_path, engine="edenspark")
    pack = build_pipeline_pack(load_studio_mission(mission))
    assert pack["godot_capture"]["supported"] is False
    assert pack["godot_capture"]["command_template"] is None
    project, adapter = _adapter(tmp_path)
    with pytest.raises(ValueError, match="Godot only"):
        _result(tmp_path, project, mission, adapter)


def test_synthetic_complete_receipts_are_only_ready_for_qa(tmp_path: Path) -> None:
    # A synthetic unit fixture tests path and hash behavior, NOT a live engine run.
    mission = _mission(tmp_path)
    project, adapter = _adapter(tmp_path)
    result = _result(tmp_path, project, mission, adapter)
    assert result["status"] == "READY_FOR_QA"
    assert result["failures"] == []
    assert result["cockpit_qa_completed"] is False
    assert result["promotion_eligible"] is False
    assert len(result["verified_files"]) == 6
    assert result["verified_files"][0]["sha256"] == sha256((adapter.parent / "godot-preflight.log").read_bytes()).hexdigest()


@pytest.mark.parametrize("check", ["godot_process_passed", "png_frames_valid", "direct_media_reaches_finding"])
def test_failed_adapter_criterion_requires_iteration(tmp_path: Path, check: str) -> None:
    mission = _mission(tmp_path)
    project, adapter = _adapter(tmp_path)
    payload = json.loads(adapter.read_text())
    payload["criteria"][check] = False
    adapter.write_text(json.dumps(payload))
    result = _result(tmp_path, project, mission, adapter)
    assert result["status"] == "ITERATE"
    assert any(check in x for x in result["failures"])


def test_wrong_commit_rejected(tmp_path: Path) -> None:
    mission = _mission(tmp_path)
    project, adapter = _adapter(tmp_path)
    result = _result(tmp_path, project, mission, adapter, source_sha="a" * 40)
    assert result["status"] == "ITERATE"
    assert "source revision mismatch" in result["failures"]
    assert "capture source sha mismatch" in result["failures"]


def test_missing_or_fake_screenshot_fails(tmp_path: Path) -> None:
    mission = _mission(tmp_path)
    project, adapter = _adapter(tmp_path)
    (adapter.parent / "raw-capture" / "before-swing.png").write_bytes(b"pretend screenshot")
    result = _result(tmp_path, project, mission, adapter)
    assert result["status"] == "ITERATE"
    assert "invalid PNG: raw-capture/before-swing.png" in result["failures"]


def test_tampered_capture_metadata_fails(tmp_path: Path) -> None:
    mission = _mission(tmp_path)
    project, adapter = _adapter(tmp_path)
    (adapter.parent / "raw-capture" / "capture.json").write_text(json.dumps({
        "source": {"evidence_class": "deterministic_fixture", "source_head_sha": SHA},
    }))
    result = _result(tmp_path, project, mission, adapter)
    assert result["status"] == "ITERATE"
    assert "capture is not recorded_gameplay_capture" in result["failures"]


def test_cross_project_evidence_does_not_bind(tmp_path: Path) -> None:
    mission = _mission(tmp_path)
    project, adapter = _adapter(tmp_path)
    different = tmp_path / "different"
    _file(different / "project.godot", b"project")
    result = _result(tmp_path, different, mission, adapter)
    assert result["status"] == "ITERATE"
    assert "adapter project path mismatch" in result["failures"]


def test_invalid_sha_is_explicit_error(tmp_path: Path) -> None:
    mission = _mission(tmp_path)
    project, adapter = _adapter(tmp_path)
    with pytest.raises(ValueError, match="full lowercase"):
        _result(tmp_path, project, mission, adapter, source_sha="HEAD")


def test_optional_creative_workstreams_require_integrity_receipts(tmp_path: Path) -> None:
    mission = _mission(tmp_path, tracks=["gameplay", "art", "audio"])
    project, adapter = _adapter(tmp_path)
    initial = _result(tmp_path, project, mission, adapter)
    assert initial["status"] == "ITERATE"
    assert any("missing creative output manifest" in x for x in initial["failures"])

    art = _file(project / "assets" / "art-manifest.json", b'{"assets":[]}')
    audio = _file(project / "audio" / "recipe-set.json", b'{"recipes":[]}')
    manifest = {
        "schema_version": 1,
        "mission_id": "slice-smoke-001",
        "art": {
            "source": "mado-asset-foundry",
            "path": art.relative_to(project).as_posix(),
            "sha256": sha256(art.read_bytes()).hexdigest(),
        },
        "audio": {
            "source": "mado-game-audio-loop",
            "path": audio.relative_to(project).as_posix(),
            "sha256": sha256(audio.read_bytes()).hexdigest(),
        },
    }
    receipt_file = _file(tmp_path / "creative.json", json.dumps(manifest).encode())
    report = evaluate_godot_pipeline(
        project, mission, adapter, tmp_path / "final",
        expected_source_sha=SHA, creative_manifest_path=receipt_file,
    )
    verdict = json.loads(report.read_text(encoding="utf-8"))
    assert verdict["status"] == "READY_FOR_QA"
    assert len(verdict["verified_creative_outputs"]) == 2
    assert all(not item["semantic_review_completed"] for item in verdict["verified_creative_outputs"])
    assert verdict["promotion_eligible"] is False

    _file(art, b"tampered")
    report = evaluate_godot_pipeline(
        project, mission, adapter, tmp_path / "tampered",
        expected_source_sha=SHA, creative_manifest_path=receipt_file,
    )
    verdict = json.loads(report.read_text(encoding="utf-8"))
    assert verdict["status"] == "ITERATE"
    assert "art: sha256 mismatch" in verdict["failures"]


def test_creative_receipt_path_cannot_escape_project(tmp_path: Path) -> None:
    mission = _mission(tmp_path, tracks=["gameplay", "art"])
    project, adapter = _adapter(tmp_path)
    manifest = {
        "schema_version": 1, "mission_id": "slice-smoke-001",
        "art": {"source": "mado-asset-foundry", "path": "../../outside.json", "sha256": "0" * 64},
    }
    receipt = _file(tmp_path / "creative.json", json.dumps(manifest).encode())
    report = evaluate_godot_pipeline(
        project, mission, adapter, tmp_path / "final",
        expected_source_sha=SHA, creative_manifest_path=receipt,
    )
    verdict = json.loads(report.read_text(encoding="utf-8"))
    assert verdict["status"] == "ITERATE"
    assert "art: missing file or path escape" in verdict["failures"]
