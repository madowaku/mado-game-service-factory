"""Friction motion-graphics handoff compiler and untrusted SVG export intake.

No Friction process, browser, or engine runs here. No output is release approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any
import xml.etree.ElementTree as ET

BRIEF_SCHEMA = "mgsf.motion-graphics-brief.v1"
MISSION_SCHEMA = "mgsf.motion-graphics-mission.v1"
EVAL_SCHEMA = "mgsf.motion-graphics-evaluation.v1"
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{2,63}\Z")
SVG_NS = "http://www.w3.org/2000/svg"
ANIMATIONS = {"animate", "animateTransform", "animateMotion", "set"}
MAX_SVG_BYTES = 2_000_000


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _svg_info(raw: bytes) -> tuple[ET.Element, tuple[int, int], int]:
    if len(raw) > MAX_SVG_BYTES or not raw.lstrip().startswith((b"<svg", b"<?xml")):
        raise ValueError("SVG is too large or not SVG/XML")
    # Entity/doctype expansion and scriptable references are not appropriate for web handoff.
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I):
        raise ValueError("SVG DTD/entities are not allowed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("Invalid SVG XML") from exc
    if _local_name(root.tag) != "svg" or not root.tag.startswith("{" + SVG_NS + "}"):
        raise ValueError("Expected SVG namespace")
    for node in root.iter():
        name = _local_name(node.tag).lower()
        if name in {"script", "foreignobject", "iframe"}:
            raise ValueError("Executable/embedded SVG content is not allowed")
        if name == "style" and node.text and (
            re.search(r"@import|url\s*\(\s*['\"]?(?!#)", node.text, re.I)
            or re.search(r"javascript\s*:", node.text, re.I)
        ):
            raise ValueError("External CSS references are not allowed")
        for attr, value in node.attrib.items():
            key = _local_name(attr).lower()
            if key.startswith("on") or (key in {"href", "src"} and not (
                value.startswith("#") or value.startswith("data:image/")
            )):
                raise ValueError("External/scripted SVG references are not allowed")
            if re.search(r"url\s*\(\s*['\"]?(?!#)", value, re.I):
                raise ValueError("External CSS URL is not allowed")
            if re.search(r"javascript\s*:", value, re.I):
                raise ValueError("JavaScript URLs are not allowed")
    vb = root.get("viewBox")
    if not vb:
        raise ValueError("SVG must provide a viewBox")
    try:
        x, y, width, height = [float(t) for t in re.split(r"[\s,]+", vb.strip())]
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid SVG viewBox") from exc
    if not (x == x and y == y and width.is_integer() and height.is_integer()
            and 1 <= width <= 8192 and 1 <= height <= 8192):
        raise ValueError("Invalid SVG viewBox dimensions")
    count = sum(_local_name(n.tag) in ANIMATIONS for n in root.iter())
    return root, (int(width), int(height)), count


def validate_brief(brief: dict[str, Any], source_root: Path) -> bytes:
    if brief.get("schema") != BRIEF_SCHEMA:
        raise ValueError("Unknown motion brief schema")
    if not isinstance(brief.get("id"), str) or not IDENTIFIER.fullmatch(brief["id"]):
        raise ValueError("Invalid motion ID")
    if not isinstance(brief.get("project"), str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", brief["project"]
    ):
        raise ValueError("Project must be owner/repository")
    if not isinstance(brief.get("creative_intent"), str) or not 15 <= len(brief["creative_intent"]) <= 3000:
        raise ValueError("creative_intent must be between 15 and 3000 characters")
    if brief.get("target") not in {"web_svg", "godot_png_sequence", "video"}:
        raise ValueError("Unsupported motion target")
    if not isinstance(brief.get("source_svg"), str):
        raise ValueError("source_svg required")
    source = Path(brief["source_svg"])
    if source.is_absolute() or source.suffix.lower() != ".svg":
        raise ValueError("source_svg must be a relative SVG path")
    base = source_root.resolve()
    full = (source_root / source).resolve()
    if not full.is_relative_to(base) or not full.is_file():
        raise ValueError("source_svg must exist inside brief folder")
    raw = full.read_bytes()
    root, dims, _ = _svg_info(raw)
    scene = brief.get("scene")
    if not isinstance(scene, dict) or set(scene) != {"width", "height", "fps", "frames"}:
        raise ValueError("scene requires width/height/fps/frames")
    for key, lo, hi in (("width", 32, 4096), ("height", 32, 4096),
                        ("fps", 1, 120), ("frames", 2, 1800)):
        if type(scene[key]) is not int or not lo <= scene[key] <= hi:
            raise ValueError(f"Invalid scene {key}")
    if dims != (scene["width"], scene["height"]):
        raise ValueError("Source SVG viewBox must match scene dimensions")
    for key in ("states", "acceptance"):
        values = brief.get(key)
        if not isinstance(values, list) or not values or any(
            not isinstance(v, str) or not v.strip() for v in values
        ):
            raise ValueError(f"{key} must be a nonempty string array")
    if not isinstance(brief.get("reduced_motion"), str) or not brief["reduced_motion"].strip():
        raise ValueError("Reduced-motion fallback required")
    tracks = brief.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("At least one animation track required")
    existing_ids = {n.get("id") for n in root.iter() if n.get("id")}
    for track in tracks:
        if not isinstance(track, dict) or set(track) != {"object_id", "property", "keyframes"}:
            raise ValueError("Invalid animation track")
        if track["object_id"] not in existing_ids:
            raise ValueError(f"Unknown SVG object ID: {track['object_id']}")
        if track["property"] not in {"translation", "rotation", "scale", "opacity", "shear"}:
            raise ValueError("Unsupported animation property")
        keys = track["keyframes"]
        if not isinstance(keys, list) or len(keys) < 2:
            raise ValueError("Animation tracks require >=2 keyframes")
        last = -1
        for point in keys:
            if not isinstance(point, dict) or set(point) != {"frame", "value"}:
                raise ValueError("Invalid animation keyframe")
            frame, value = point["frame"], point["value"]
            if type(frame) is not int or not 0 <= frame < scene["frames"] or frame <= last:
                raise ValueError("Keyframes must increase within scene")
            if not isinstance(value, str) or not 1 <= len(value) <= 120:
                raise ValueError("Keyframe value must be descriptive text")
            last = frame
    return raw


def create_motion_pack(brief_path: Path, output_root: Path) -> Path:
    brief = _load(brief_path)
    source = validate_brief(brief, brief_path.parent)
    scene = brief["scene"]
    tracks = "\n".join(
        f"- `{t['object_id']}` / {t['property']}: "
        + ", ".join(f"f{k['frame']}={k['value']}" for k in t["keyframes"])
        for t in brief["tracks"]
    )
    prompt = f"""# Friction 1.0.0 motion handoff: {brief['id']}

## Creative intent
{brief['creative_intent']}

## Working scene
- Target: {brief['target']}
- Dimensions: {scene['width']} x {scene['height']}
- Timeline: {scene['frames']} frames at {scene['fps']} fps
- Import `source.svg` in Friction; preserve object names and art direction.
- Create an editable `.friction` project manually. MGSF cannot generate it.
- Animate the following tracks and tune easing in the timeline/graph editor:
{tracks}

## Interaction responsibility
Friction exports a visual animation, not the interactive window state machine.
Keep click/keyboard/focus controls in the Web/Godot runtime. Use a static open-state
fallback and make the transition interruptible. Do not make SVG animation the only
way to understand the changed state.

## Reduced-motion contract
{brief['reduced_motion']}

## Acceptance checks
""" + "".join(f"- {x}\n" for x in brief["acceptance"]) + """
## Export and evidence
- Web: Export animated SVG (SMIL). Confirm visual fidelity in target browsers.
- Godot: Export numbered transparent PNG sequence and import as runtime frames.
- Video: Use MP4/WebM as appropriate.
- Friction's SVG exporter supports only a subset of its effects; visually inspect output.
- Keep original `.friction` source and manually recorded export settings alongside output.
- `mgsf motion-graphics-eval` checks SVG structure and SHA only. It cannot certify
  a Friction render, browser playback, licensing, performance, or human art review.
"""
    manifest = {
        "schema": MISSION_SCHEMA,
        "id": brief["id"],
        "brief": brief,
        "brief_sha256": _digest(_canonical(brief)),
        "source_sha256": _digest(source),
        "prompt_sha256": _digest(prompt.encode("utf-8")),
        "state": "NOT_EXECUTED",
        "evidence_class": "deterministic_motion_handoff",
        "promotion": "HOLD_UNTIL_REAL_EXPORT_AND_BROWSER_REVIEW",
    }
    folder = output_root / brief["id"]
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "source.svg").write_bytes(source)
    (folder / "MOTION_HANDOFF.md").write_text(prompt, encoding="utf-8")
    (folder / "mission.json").write_bytes(_canonical(manifest))
    return folder


def evaluate_svg_export(mission_dir: Path, exported_svg: Path, output_root: Path) -> Path:
    mission = _load(mission_dir / "mission.json")
    if mission.get("schema") != MISSION_SCHEMA:
        raise ValueError("Unknown mission schema")
    brief = mission.get("brief")
    if not isinstance(brief, dict) or mission.get("brief_sha256") != _digest(_canonical(brief)):
        raise ValueError("Mission contents changed")
    if mission.get("id") != brief.get("id"):
        raise ValueError("Mission ID mismatch")
    if brief.get("target") != "web_svg":
        raise ValueError("SVG evaluator supports web_svg targets only")
    source = (mission_dir / "source.svg").read_bytes()
    if _digest(source) != mission.get("source_sha256"):
        raise ValueError("Source SVG integrity mismatch")
    if _digest((mission_dir / "MOTION_HANDOFF.md").read_bytes()) != mission.get("prompt_sha256"):
        raise ValueError("Mission handoff integrity mismatch")
    raw = exported_svg.read_bytes()
    _, dims, animation_count = _svg_info(raw)
    scene = brief["scene"]
    if dims != (scene["width"], scene["height"]):
        raise ValueError("Export SVG viewBox does not match mission")
    status = "READY_FOR_HUMAN_REVIEW" if animation_count else "HOLD"
    evidence = {
        "schema": EVAL_SCHEMA,
        "mission_id": mission["id"],
        "origin": "operator_supplied_unverified_svg",
        "export_sha256": _digest(raw),
        "export_bytes": len(raw),
        "scene": scene,
        "smil_animation_elements": animation_count,
        "verdict": status,
        "release_approved": False,
        "checks_remaining": [
            "Confirm exported media actually came from Friction and retain source project",
            "Verify animation in real browsers/engine, including reduced motion",
            "Verify click, keyboard, focus, interruption, timing, and mobile performance",
            "Review artistic quality, accessibility, asset licensing, and packaging",
        ],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"{mission['id']}-evaluation.json"
    path.write_bytes(_canonical(evidence))
    return path
