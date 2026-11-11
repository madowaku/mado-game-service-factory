import hashlib
import json
from pathlib import Path

import pytest

from mgsf.motion_graphics_bridge import (
    EVAL_SCHEMA,
    create_motion_pack,
    evaluate_svg_export,
    validate_brief,
)

FIXTURES = Path("fixtures/motion-graphics")
BRIEF = FIXTURES / "madowaku-window-opening-001.json"


def _create(tmp_path):
    return create_motion_pack(BRIEF, tmp_path / "missions")


def _export(tmp_path, *, animate=True, malicious=False, width=640):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 480"><rect width="10" height="10">'
    if animate:
        svg += '<animate attributeName="opacity" from="0" to="1" dur="1s" />'
    svg += '</rect></svg>'
    if malicious:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"><script>alert(1)</script></svg>'
    path = tmp_path / "friction-export.svg"
    path.write_text(svg, encoding="utf-8")
    return path


def test_pack_creates_handoff_but_does_not_claim_render(tmp_path):
    folder = _create(tmp_path)
    mission = json.loads((folder / "mission.json").read_text(encoding="utf-8"))
    assert mission["state"] == "NOT_EXECUTED"
    assert mission["promotion"].startswith("HOLD_")
    assert (folder / "source.svg").read_bytes() == (FIXTURES / "madowaku-window-source.svg").read_bytes()
    assert "Friction 1.0.0" in (folder / "MOTION_HANDOFF.md").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        _create(tmp_path)


def test_reject_asset_path_escape():
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    brief["source_svg"] = "../../secrets.svg"
    with pytest.raises(ValueError, match="inside brief folder"):
        validate_brief(brief, FIXTURES)


def test_reject_nonexistent_svg_object():
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    brief["tracks"][0]["object_id"] = "missing-object"
    with pytest.raises(ValueError, match="Unknown SVG object"):
        validate_brief(brief, FIXTURES)


def test_reject_reverse_keyframes():
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    brief["tracks"][0]["keyframes"][1]["frame"] = 0
    with pytest.raises(ValueError, match="increase"):
        validate_brief(brief, FIXTURES)


def test_svg_export_is_review_only(tmp_path):
    mission = _create(tmp_path)
    svg = _export(tmp_path)
    eval_path = evaluate_svg_export(mission, svg, tmp_path / "evidence")
    obj = json.loads(eval_path.read_text(encoding="utf-8"))
    assert obj["schema"] == EVAL_SCHEMA
    assert obj["verdict"] == "READY_FOR_HUMAN_REVIEW"
    assert obj["origin"] == "operator_supplied_unverified_svg"
    assert obj["release_approved"] is False
    assert obj["export_sha256"] == hashlib.sha256(svg.read_bytes()).hexdigest()
    assert obj["smil_animation_elements"] == 1


def test_static_export_stays_hold(tmp_path):
    mission = _create(tmp_path)
    svg = _export(tmp_path, animate=False)
    obj = json.loads(evaluate_svg_export(mission, svg, tmp_path / "evidence").read_text(encoding="utf-8"))
    assert obj["verdict"] == "HOLD"


def test_export_size_mismatch_rejected(tmp_path):
    mission = _create(tmp_path)
    svg = _export(tmp_path, width=800)
    with pytest.raises(ValueError, match="viewBox"):
        evaluate_svg_export(mission, svg, tmp_path / "evidence")


def test_svg_scripts_rejected(tmp_path):
    mission = _create(tmp_path)
    svg = _export(tmp_path, malicious=True)
    with pytest.raises(ValueError, match="Executable"):
        evaluate_svg_export(mission, svg, tmp_path / "evidence")


def test_source_tamper_rejected(tmp_path):
    mission = _create(tmp_path)
    (mission / "source.svg").write_text("tamper", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        evaluate_svg_export(mission, _export(tmp_path), tmp_path / "evidence")


def test_prompt_tamper_rejected(tmp_path):
    mission = _create(tmp_path)
    (mission / "MOTION_HANDOFF.md").write_text("tamper", encoding="utf-8")
    with pytest.raises(ValueError, match="handoff integrity"):
        evaluate_svg_export(mission, _export(tmp_path), tmp_path / "evidence")
