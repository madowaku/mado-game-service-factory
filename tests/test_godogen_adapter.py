from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from mgsf import godogen_adapter as adapter


def _upstream(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "godogen"
    (source / "prompts").mkdir(parents=True)
    (source / "engines").mkdir()
    (source / "asset-gen" / "tools").mkdir(parents=True)
    (source / "prompts/runtime.md").write_text(
        "Build " + "$" + "{ENGINE_NAME}" + " using " + "$" + "{ASSET_SKILL_COMMAND}"
        + " and " + "$" + "{ENGINE_GUIDE_FILE}", encoding="utf-8",
    )
    (source / "engines/godot.md").write_text("Godot 4 .NET C# guide", encoding="utf-8")
    (source / "LICENSE.md").write_text("MIT License", encoding="utf-8")
    (source / "asset-gen/SKILL.md").write_text(
        "Use " + "$" + "{ASSET_GEN_SKILL_DIR}" + " for assets", encoding="utf-8",
    )
    (source / "asset-gen/tools/sample.py").write_text("print('never executed')", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "fixture"], check=True,
    )
    sha = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    return source, sha


def _mission(tmp_path: Path) -> dict:
    return {"schema_version": 1, "mission_id": "godogen-mission",
            "description": "Build a keyboard-operated test game",
            "success_criteria": ["visible player motion"], "max_iterations": 2}


def _result(tmp_path: Path, mission: dict, proof: str = "screenshots/proof.mp4") -> Path:
    path = tmp_path / "result.json"
    path.write_text(json.dumps({
        "mission_id": mission["mission_id"],
        **{key: True for key in adapter.RESULT_FIELDS},
        "runtime_errors": [], "observations": ["played"],
        "proof_video": proof,
    }), encoding="utf-8")
    return path


def _runner() -> dict:
    return {
        "runner": "codex-exec", "returncode": 0,
        "engine_checks": {name: {"returncode": 0} for name in
                          ("dotnet_build", "godot_import", "godot_launch")},
    }


def test_intake_previews_without_writing_and_stages_pinned_docs(tmp_path: Path) -> None:
    source, sha = _upstream(tmp_path)
    target = tmp_path / "new-game"
    preview = adapter.intake_godogen(source, target, sha)
    assert preview["status"] == "PREVIEW"
    assert not target.exists()

    staged = adapter.intake_godogen(source, target, sha, dry_run=False)
    assert staged["status"] == "STAGED"
    assert (target / "AGENTS.md").read_text() == "Build Godot using $asset-gen and godot.md"
    assert ".agents/skills/asset-gen" in (
        target / ".agents/skills/asset-gen/SKILL.md"
    ).read_text()
    assert (target / ".mgsf/upstream/LICENSE.md").read_text() == "MIT License"
    assert not (target / "project.godot").exists()
    assert staged["policy"]["upstream_publish_script_executed"] is False
    assert staged["source_files"]["prompts/runtime.md"] == adapter._sha(source / "prompts/runtime.md")


def test_intake_refuses_unpinned_dirty_or_existing_target(tmp_path: Path) -> None:
    source, sha = _upstream(tmp_path)
    with pytest.raises(adapter.GodogenError, match="pinned"):
        adapter.intake_godogen(source, tmp_path / "unused", "0" * 40)
    (source / "new-untracked.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(adapter.GodogenError, match="clean"):
        adapter.intake_godogen(source, tmp_path / "unused", sha)
    (source / "new-untracked.txt").unlink()
    target = tmp_path / "existing"
    target.mkdir()
    (target / "important.txt").write_text("preserve me", encoding="utf-8")
    with pytest.raises(adapter.GodogenError, match="already exists"):
        adapter.intake_godogen(source, target, sha, dry_run=False)
    assert (target / "important.txt").read_text() == "preserve me"


def test_intake_rejects_symlinks_and_overlapping_roots(tmp_path: Path) -> None:
    source, sha = _upstream(tmp_path)
    with pytest.raises(adapter.GodogenError, match="disjoint"):
        adapter.intake_godogen(source, source / "nested", sha)
    (source / "asset-gen/link").symlink_to(source / "LICENSE.md")
    with pytest.raises(adapter.GodogenError, match="clean"):
        adapter.intake_godogen(source, tmp_path / "target", sha)


def test_mission_schema_is_bounded(tmp_path: Path) -> None:
    mission = _mission(tmp_path)
    path = tmp_path / "mission.json"
    path.write_text(json.dumps(mission), encoding="utf-8")
    assert adapter.load_mission(path)["max_iterations"] == 2
    mission["max_iterations"] = 100
    path.write_text(json.dumps(mission), encoding="utf-8")
    with pytest.raises(adapter.GodogenError, match="max_iterations"):
        adapter.load_mission(path)


def test_fixture_never_promotes_even_if_everything_claims_success(
    tmp_path: Path, monkeypatch,
) -> None:
    project = tmp_path / "game"
    (project / "screenshots").mkdir(parents=True)
    (project / "project.godot").write_text("", encoding="utf-8")
    (project / "game.csproj").write_text("", encoding="utf-8")
    (project / "screenshots/proof.mp4").write_bytes(b"fake video")
    mission = _mission(tmp_path)
    result_path = _result(tmp_path, mission)
    monkeypatch.setattr(adapter, "_verify_video", lambda *args: (True, {"duration_seconds": 16}))
    evaluation = adapter.evaluate_godogen(
        project, mission, result_path, _runner(), tmp_path / "evidence", fixture=True,
    )
    assert evaluation.status == "HOLD"
    assert evaluation.artifact_count == 1
    evidence = json.loads((evaluation.root / "evaluation.json").read_text(encoding="utf-8"))
    assert evidence["evidence_class"] == "deterministic_godogen_fixture"
    assert evidence["video"][0]["sha256"] == adapter._sha(evaluation.root / "proof.mp4")


def test_without_independent_engine_probes_live_claim_is_held(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    (project / "screenshots").mkdir(parents=True)
    (project / "project.godot").write_text("", encoding="utf-8")
    (project / "game.csproj").write_text("", encoding="utf-8")
    (project / "screenshots/proof.mp4").write_bytes(b"fake video")
    monkeypatch.setattr(adapter, "_verify_video", lambda *args: (True, {}))
    mission = _mission(tmp_path)
    evaluation = adapter.evaluate_godogen(
        project, mission, _result(tmp_path, mission),
        {"runner": "codex-exec", "returncode": 0}, tmp_path / "evidence",
    )
    assert evaluation.status == "HOLD"


def test_missing_or_escaped_proof_cannot_pass(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "game"
    (project / "screenshots").mkdir(parents=True)
    (project / "project.godot").write_text("", encoding="utf-8")
    (project / "game.csproj").write_text("", encoding="utf-8")
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"not game proof")
    (project / "screenshots/proof.mp4").symlink_to(outside)
    monkeypatch.setattr(adapter, "_verify_video", lambda *args: (True, {}))
    mission = _mission(tmp_path)
    evaluation = adapter.evaluate_godogen(
        project, mission, _result(tmp_path, mission), _runner(), tmp_path / "evidence",
    )
    assert evaluation.status == "ITERATE"
    assert evaluation.artifact_count == 0


def test_complete_mocked_contract_passes_but_is_not_claimed_as_human_playtest(
    tmp_path: Path, monkeypatch,
) -> None:
    project = tmp_path / "game"
    (project / "screenshots").mkdir(parents=True)
    (project / "project.godot").write_text("", encoding="utf-8")
    (project / "game.csproj").write_text("", encoding="utf-8")
    (project / "screenshots/proof.mp4").write_bytes(b"mock media")
    monkeypatch.setattr(adapter, "_verify_video", lambda *args: (True, {"duration_seconds": 17}))
    mission = _mission(tmp_path)
    evaluation = adapter.evaluate_godogen(
        project, mission, _result(tmp_path, mission), _runner(), tmp_path / "evidence",
    )
    assert evaluation.status == "PASS"
    evidence = json.loads((evaluation.root / "evaluation.json").read_text(encoding="utf-8"))
    assert "not a human playtest" in evidence["provenance_note"]
    assert evidence["checks"]["independent_engine_checks"] is True
