from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from mgsf.creative_lab import CreativeLabError, run_creative_qa


FIXTURE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_creative_lab_fixture.py"


def fixture_run(tmp_path: Path) -> Path:
    target = tmp_path / "creative-run"
    subprocess.run([sys.executable, str(FIXTURE_SCRIPT), str(target)], check=True,
                   capture_output=True, text=True)
    return target


def load_manifest(root: Path) -> dict:
    return json.loads((root / "run.json").read_text(encoding="utf-8"))


def save_manifest(root: Path, payload: dict) -> None:
    (root / "run.json").write_text(json.dumps(payload), encoding="utf-8")


def test_fixture_produces_hashed_structural_pass_but_never_promotion(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    before = {path.relative_to(source): path.read_bytes()
              for path in source.rglob("*") if path.is_file()}
    result = run_creative_qa(source, tmp_path / "evidence")
    report = json.loads(result.evidence_path.read_text(encoding="utf-8"))
    assert result.structural_status == "PASS"
    assert result.promotion_status == "HOLD"
    assert report["promotion_gate"]["status"] == "HOLD"
    assert report["source"]["evidence_class"] == "deterministic_fixture"
    assert report["metrics"]["glb"]["meshes"] == 1
    assert report["metrics"]["frame_count"] == 2
    assert report["metrics"]["unique_frame_count"] == 2
    assert report["metrics"]["frame_size"] == [128, 128]
    assert all(item["sha256"] == hashlib.sha256(
        (source / item["path"]).read_bytes()).hexdigest()
        for item in report["file_index"])
    assert before == {path.relative_to(source): path.read_bytes()
                      for path in source.rglob("*") if path.is_file()}


def test_repeated_run_must_not_overwrite_prior_evidence(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    run_creative_qa(source, tmp_path / "evidence")
    with pytest.raises(CreativeLabError, match="overwrite"):
        run_creative_qa(source, tmp_path / "evidence")


@pytest.mark.parametrize("bad_name", [
    "../outside.png", "/tmp/outside.png", "frames/../reference.png",
    "frames\\000.png", "frames//000.png",
])
def test_path_traversal_and_noncanonical_paths_fail(tmp_path: Path, bad_name: str) -> None:
    source = fixture_run(tmp_path)
    manifest = load_manifest(source)
    manifest["frames"][0] = bad_name
    save_manifest(source, manifest)
    with pytest.raises(CreativeLabError):
        run_creative_qa(source, tmp_path / "evidence")
    assert not (tmp_path / "evidence" / "creative-qa").exists()


def test_symlink_frame_is_rejected(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    first = source / "frames" / "000.png"
    outside = tmp_path / "outside.png"
    outside.write_bytes(first.read_bytes())
    first.unlink()
    try:
        first.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation requires permission")
    with pytest.raises(CreativeLabError, match="Symlink"):
        run_creative_qa(source, tmp_path / "evidence")


def test_static_frames_fail_instead_of_being_called_animation(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    (source / "frames" / "001.png").write_bytes((source / "frames" / "000.png").read_bytes())
    with pytest.raises(CreativeLabError, match="distinct"):
        run_creative_qa(source, tmp_path / "evidence")


def test_truncated_glb_fails_closed(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    scene = source / "scene.glb"
    scene.write_bytes(scene.read_bytes()[:-7])
    with pytest.raises(CreativeLabError, match="GLB"):
        run_creative_qa(source, tmp_path / "evidence")


def test_provenance_and_rights_must_be_explicit(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    manifest = load_manifest(source)
    manifest["source"]["evidence_class"] = "recorded_gameplay_capture"
    save_manifest(source, manifest)
    with pytest.raises(CreativeLabError, match="evidence_class"):
        run_creative_qa(source, tmp_path / "evidence")
    manifest["source"]["evidence_class"] = "operator_supplied_local_render"
    manifest["rights"]["license"] = ""
    save_manifest(source, manifest)
    with pytest.raises(CreativeLabError, match="rights.license"):
        run_creative_qa(source, tmp_path / "evidence")


def test_operator_supplied_render_still_holds_for_review(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    manifest = load_manifest(source)
    manifest["source"]["evidence_class"] = "operator_supplied_local_render"
    manifest["rights"] = {"license": "MIT", "reviewed": True}
    save_manifest(source, manifest)
    result = run_creative_qa(source, tmp_path / "evidence")
    assert result.promotion_status == "HOLD"


def test_output_cannot_mutate_source_tree(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    with pytest.raises(CreativeLabError, match="inside the source"):
        run_creative_qa(source, source / "generated")


def test_duplicate_frame_references_fail(tmp_path: Path) -> None:
    source = fixture_run(tmp_path)
    manifest = load_manifest(source)
    manifest["frames"][1] = manifest["frames"][0]
    save_manifest(source, manifest)
    with pytest.raises(CreativeLabError, match="Duplicate frame"):
        run_creative_qa(source, tmp_path / "evidence")
