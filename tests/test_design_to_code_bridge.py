import hashlib
import json
from pathlib import Path
import struct
import zlib

import pytest

from mgsf.design_to_code_bridge import (
    RECEIPT_SCHEMA,
    create_mission_pack,
    evaluate_render_receipt,
    validate_brief,
)


def _brief() -> dict:
    return json.loads(
        Path("fixtures/design-to-code/madowaku-window-portal-001.json")
        .read_text(encoding="utf-8")
    )


def _build_mission(tmp_path: Path) -> Path:
    path = tmp_path / "brief.json"
    path.write_text(json.dumps(_brief()), encoding="utf-8")
    return create_mission_pack(path, tmp_path / "missions")


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    row = b"\x00" + b"\x80\x60\x40" * width
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height))
            + chunk(b"IEND", b""))


def _receipt(tmp_path: Path, mission: Path, *, origin: str = "fixture") -> Path:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    screenshots = []
    for state, width, height in (("desktop", 480, 320), ("mobile", 390, 480)):
        image = _png(width, height)
        filename = state + ".png"
        (project / filename).write_bytes(image)
        screenshots.append({
            "state": state, "path": filename,
            "sha256": hashlib.sha256(image).hexdigest(),
            "width": width, "height": height,
        })
    manifest = json.loads((mission / "mission.json").read_text(encoding="utf-8"))
    record = {
        "schema": RECEIPT_SCHEMA, "mission_id": manifest["id"],
        "prompt_sha256": manifest["prompt_sha256"],
        "origin": origin, "screenshots": screenshots,
    }
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_plan_preserves_creative_intent_and_pins_upstream(tmp_path: Path) -> None:
    mission = _build_mission(tmp_path)
    manifest = json.loads((mission / "mission.json").read_text(encoding="utf-8"))
    prompt = (mission / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert manifest["state"] == "NOT_EXECUTED"
    assert len(manifest["upstream"]["commit"]) == 40
    assert manifest["promotion"].startswith("HOLD_")
    assert "hand-drawn windows" in prompt
    assert "two passes" in prompt
    assert "NOT universal" in prompt
    with pytest.raises(FileExistsError):
        _build_mission(tmp_path)


def test_reference_mode_requires_reference() -> None:
    brief = _brief()
    brief["source_mode"] = "reference_reconstruction"
    with pytest.raises(ValueError, match="authoritative reference"):
        validate_brief(brief)


def test_reject_unsafe_mission_id() -> None:
    brief = _brief()
    brief["id"] = "../../oops"
    with pytest.raises(ValueError, match="mission ID"):
        validate_brief(brief)


def test_fixture_evidence_must_hold(tmp_path: Path) -> None:
    mission = _build_mission(tmp_path)
    receipt = _receipt(tmp_path, mission)
    path = evaluate_render_receipt(
        mission, receipt, tmp_path / "project", tmp_path / "out"
    )
    evaluation = json.loads(path.read_text(encoding="utf-8"))
    assert evaluation["verdict"] == "HOLD"
    assert evaluation["release_approved"] is False
    assert len(evaluation["screenshots_verified"]) == 2


def test_browser_capture_is_review_required_not_pass(tmp_path: Path) -> None:
    mission = _build_mission(tmp_path)
    receipt = _receipt(tmp_path, mission, origin="browser_capture")
    evaluation = json.loads(evaluate_render_receipt(
        mission, receipt, tmp_path / "project", tmp_path / "out"
    ).read_text(encoding="utf-8"))
    assert evaluation["verdict"] == "READY_FOR_HUMAN_REVIEW"
    assert evaluation["release_approved"] is False
    assert evaluation["browser_capture_self_attested"] is True


def test_reject_changed_screenshot(tmp_path: Path) -> None:
    mission = _build_mission(tmp_path)
    receipt = _receipt(tmp_path, mission)
    (tmp_path / "project" / "desktop.png").write_bytes(b"forged")
    with pytest.raises(ValueError, match="integrity mismatch"):
        evaluate_render_receipt(mission, receipt, tmp_path / "project", tmp_path / "out")


def test_reject_escaping_screenshot_path(tmp_path: Path) -> None:
    mission = _build_mission(tmp_path)
    receipt = _receipt(tmp_path, mission)
    record = json.loads(receipt.read_text(encoding="utf-8"))
    record["screenshots"][0]["path"] = "../secret.png"
    receipt.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="project-relative"):
        evaluate_render_receipt(mission, receipt, tmp_path / "project", tmp_path / "out")


def test_reject_tampered_prompt(tmp_path: Path) -> None:
    mission = _build_mission(tmp_path)
    receipt = _receipt(tmp_path, mission)
    (mission / "AGENT_PROMPT.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="Mission prompt changed"):
        evaluate_render_receipt(mission, receipt, tmp_path / "project", tmp_path / "out")
