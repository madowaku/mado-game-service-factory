"""Offline, provenance-aware 3D and motion evidence inspection.

This module NEVER runs third-party Three.js/Blender code, calls a model/API, or
claims that structural checks demonstrate visual fidelity or Godot compatibility.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FRAMES = 240
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
EVIDENCE_CLASSES = {"deterministic_fixture", "operator_supplied_local_render"}


class CreativeLabError(ValueError):
    """An unsafe, incomplete, or structurally invalid creative run."""


@dataclass(frozen=True)
class CreativeQaRun:
    evidence_path: Path
    structural_status: str
    promotion_status: str


def _json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CreativeLabError(f"Invalid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise CreativeLabError(f"JSON root must be an object: {path}")
    return data


def _artifact(root: Path, name: Any, suffixes: set[str]) -> Path:
    if not isinstance(name, str) or not name or "\\" in name:
        raise CreativeLabError("Artifact paths must be nonempty POSIX-relative strings")
    rel = PurePosixPath(name)
    if rel.is_absolute() or any(piece in {"", ".", ".."} for piece in name.split("/")):
        raise CreativeLabError(f"Unsafe artifact path: {name}")
    path = root.joinpath(*rel.parts)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
        raise CreativeLabError(f"Symlink artifact is prohibited: {name}")
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise CreativeLabError(f"Missing or unsupported artifact: {name}")
    size = path.stat().st_size
    if size == 0 or size > MAX_FILE_BYTES:
        raise CreativeLabError(f"Artifact must be 1..{MAX_FILE_BYTES} bytes: {name}")
    return path


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise CreativeLabError(f"Not a PNG with an IHDR header: {path.name}")
    width, height = struct.unpack(">II", header[16:24])
    if not (1 <= width <= 8192 and 1 <= height <= 8192):
        raise CreativeLabError(f"PNG dimensions out of bounds: {path.name}")
    return width, height


def _glb_scene(path: Path) -> dict[str, int]:
    raw = path.read_bytes()
    if len(raw) < 28:
        raise CreativeLabError("GLB is too short")
    magic, version, total = struct.unpack_from("<4sII", raw)
    if magic != b"glTF" or version != 2 or total != len(raw):
        raise CreativeLabError("GLB header/version/length is invalid")
    offset = 12
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(raw):
        if len(raw) - offset < 8:
            raise CreativeLabError("GLB truncated chunk header")
        length, kind = struct.unpack_from("<I4s", raw, offset)
        offset += 8
        if length % 4 or length > len(raw) - offset:
            raise CreativeLabError("GLB invalid chunk length")
        chunks.append((kind, raw[offset : offset + length]))
        offset += length
    if not chunks or chunks[0][0] != b"JSON" or not any(k == b"BIN\x00" for k, _ in chunks[1:]):
        raise CreativeLabError("GLB must have JSON and BIN chunks")
    try:
        scene = json.loads(chunks[0][1].decode("utf-8").rstrip(" \x00"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CreativeLabError("Invalid GLB JSON") from exc
    if not isinstance(scene, dict) or scene.get("asset", {}).get("version") != "2.0":
        raise CreativeLabError("GLB must declare glTF 2.0")
    meshes = scene.get("meshes", [])
    nodes = scene.get("nodes", [])
    accessors = scene.get("accessors", [])
    buffers = scene.get("buffers", [])
    if not (isinstance(meshes, list) and meshes and isinstance(nodes, list) and nodes):
        raise CreativeLabError("GLB has no meshes/nodes")
    if not (isinstance(accessors, list) and accessors and isinstance(buffers, list) and buffers):
        raise CreativeLabError("GLB has no accessors/buffers")
    if not any(isinstance(node, dict) and isinstance(node.get("mesh"), int)
               and 0 <= node["mesh"] < len(meshes) for node in nodes):
        raise CreativeLabError("GLB nodes do not reference valid meshes")
    primitives = [p for mesh in meshes if isinstance(mesh, dict)
                  for p in mesh.get("primitives", []) if isinstance(p, dict)]
    if not primitives or not all(
        isinstance(p.get("attributes"), dict)
        and isinstance(p["attributes"].get("POSITION"), int)
        and 0 <= p["attributes"]["POSITION"] < len(accessors)
        for p in primitives
    ):
        raise CreativeLabError("GLB lacks usable POSITION accessors")
    return {"meshes": len(meshes), "nodes": len(nodes),
            "primitives": len(primitives), "animations": len(scene.get("animations", []))}


def run_creative_qa(run_root: str | Path, output_root: str | Path = "evidence") -> CreativeQaRun:
    """Inspect operator-provided files without executing or altering them.

    Structural PASS is not promotion approval. The incubation gate is always HOLD.
    Invalid evidence fails closed with a CreativeLabError, before writing any report.
    """
    root = Path(run_root).resolve(strict=True)
    if not root.is_dir():
        raise CreativeLabError("Run root must be a directory")
    out = Path(output_root).resolve()
    if out == root or root in out.parents:
        raise CreativeLabError("Evidence output cannot be inside the source run")

    manifest_file = _artifact(root, "run.json", {".json"})
    run = _json_object(manifest_file)
    if run.get("schema_version") != 1:
        raise CreativeLabError("schema_version must be 1")
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise CreativeLabError("run_id must be a safe 2..64 character slug")
    source = run.get("source")
    if not isinstance(source, dict) or source.get("evidence_class") not in EVIDENCE_CLASSES:
        raise CreativeLabError("source.evidence_class must disclose evidence provenance")
    if not isinstance(source.get("generator"), str) or not source["generator"].strip():
        raise CreativeLabError("source.generator is required")
    rights = run.get("rights")
    if not isinstance(rights, dict) or not isinstance(rights.get("license"), str) or not rights["license"].strip():
        raise CreativeLabError("Explicit rights.license (or 'unknown') is required")
    if type(rights.get("reviewed")) is not bool:
        raise CreativeLabError("rights.reviewed must be a boolean")

    reference = _artifact(root, run.get("reference_image"), {".png"})
    scene_file = _artifact(root, run.get("scene"), {".glb"})
    frames = run.get("frames")
    if not isinstance(frames, list) or not (2 <= len(frames) <= MAX_FRAMES):
        raise CreativeLabError("frames must contain 2..240 PNGs")
    if len(set(map(str, frames))) != len(frames):
        raise CreativeLabError("Duplicate frame paths")
    if run.get("source_code") is not None:
        code = _artifact(root, run["source_code"], {".js", ".ts"})
    else:
        code = None

    files = [("manifest", manifest_file), ("reference", reference), ("scene", scene_file)]
    if code is not None:
        files.append(("source_code", code))
    files.extend(("frame", _artifact(root, name, {".png"})) for name in frames)
    image_size = _png_size(files[1][1])
    frame_sizes = [_png_size(path) for role, path in files if role == "frame"]
    if len(set(frame_sizes)) != 1:
        raise CreativeLabError("All render frames must have matching dimensions")
    metadata = _glb_scene(scene_file)
    indexed = [
        {"role": role, "path": path.relative_to(root).as_posix(),
         "bytes": path.stat().st_size, "sha256": _hash(path)}
        for role, path in files
    ]
    frame_hashes = [row["sha256"] for row in indexed if row["role"] == "frame"]
    if len(set(frame_hashes)) < 2:
        raise CreativeLabError("At least two frames must have distinct bytes")

    target = out / "creative-qa" / run_id
    if target.exists():
        raise CreativeLabError(f"Refusing to overwrite existing evidence: {target}")
    target.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1,
        "service": "creative-3d-motion-qa",
        "run_id": run_id,
        "structural_status": "PASS",
        "source": source,
        "rights": rights,
        "file_index": indexed,
        "metrics": {
            "reference_size": list(image_size),
            "frame_size": list(frame_sizes[0]),
            "frame_count": len(frame_hashes),
            "unique_frame_count": len(set(frame_hashes)),
            "glb": metadata,
        },
        "checks": {
            "glb_header_and_basic_scene_structure": True,
            "png_headers_and_consistent_frame_dimensions": True,
            "distinct_frame_bytes": True,
            "sha256_index_present": True,
            "source_claim_is_not_independently_verified": True,
        },
        "promotion_gate": {
            "status": "HOLD",
            "reasons": [
                "Incubation: fixture or operator assertion is not engine-run proof",
                "Real Godot GLB import and on-screen playback need independent evidence",
                "Human visual/fidelity review is required",
                "Source and dependency license approval is required",
            ],
        },
        "limitations": [
            "No Three.js/Blender code execution or network access",
            "No perceptual similarity or artistic quality measurement",
            "No full PNG decode or glTF validator; basic header/structure checks only",
            "Rendered images are not direct gameplay captures",
        ],
    }
    result = target / "creative-qa-evidence.json"
    result.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return CreativeQaRun(evidence_path=result, structural_status="PASS", promotion_status="HOLD")
