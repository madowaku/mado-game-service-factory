"""Offline MOSS-Image Layout handoff and hash-bound candidate review."""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import Any

from .vendor.moss_compile_prompt import compile_prompt, reject_constant, unique_object

MODELS = {"base": "OpenMOSS-Team/MOSS-Image-Base", "sft": "OpenMOSS-Team/MOSS-Image-SFT"}
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"),
                        object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("expected a JSON object")
    return result


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def plan_visual_asset(draft_path: Path, output_root: Path, *, model: str = "sft") -> Path:
    """Use the pinned upstream compiler; do not call a model or the network."""
    if model not in MODELS:
        raise ValueError("unknown MOSS-Image model")
    draft_path = Path(draft_path)
    source = draft_path.read_bytes()
    draft = read_json(draft_path)
    if "caption" in draft:
        raise ValueError("M1.5 needs Layout with explicit dimensions, not caption-only")
    prompt = compile_prompt(draft)
    root = Path(output_root) / draft_path.stem
    root.mkdir(parents=True, exist_ok=False)
    (root / "draft.json").write_bytes(source)
    prompt_bytes = (prompt + "\n").encode("utf-8")
    (root / "prompt.txt").write_bytes(prompt_bytes)
    write_json(root / "manifest.json", {
        "schema_version": 1,
        "service": "moss-visual-asset-intelligence",
        "lifecycle": "incubation",
        "status": "PLANNED",
        "evidence_class": "deterministic_prompt_compilation",
        "model_declared": MODELS[model],
        "inference_executed": False,
        "publication_authorized": False,
        "canvas": {"width": draft["width"], "height": draft["height"]},
        "expected_visible_text": [item["text"] for item in draft["items"]
                                  if item["label"] == "text"],
        "draft_sha256": digest(source),
        "prompt_sha256": digest(prompt_bytes),
    })
    return root


def png_size(data: bytes) -> tuple[int, int]:
    """Validate PNG chunks and CRC without inferring visual quality."""
    if not data.startswith(PNG_HEADER):
        raise ValueError("not a PNG")
    at = len(PNG_HEADER)
    dims = None
    idat = False
    finished = False
    while at + 12 <= len(data):
        size = struct.unpack_from(">I", data, at)[0]
        end = at + 12 + size
        if end > len(data):
            raise ValueError("truncated PNG chunk")
        kind = data[at + 4:at + 8]
        payload = data[at + 8:at + 8 + size]
        crc = struct.unpack_from(">I", data, at + 8 + size)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise ValueError("PNG CRC mismatch")
        if dims is None:
            if kind != b"IHDR" or size != 13:
                raise ValueError("missing PNG IHDR")
            dims = struct.unpack_from(">II", payload)
            if min(dims) <= 0:
                raise ValueError("invalid PNG dimensions")
        elif kind == b"IHDR":
            raise ValueError("duplicate PNG IHDR")
        if kind == b"IDAT":
            idat = True
        if kind == b"IEND":
            if size or not idat or end != len(data):
                raise ValueError("invalid PNG ending")
            finished = True
            break
        at = end
    if not finished or dims is None:
        raise ValueError("incomplete PNG")
    return dims


def evaluate_visual_asset(bundle: Path, *, image: Path | None = None,
                          review: Path | None = None) -> dict[str, Any]:
    """PASS means one manually accepted candidate, never service promotion."""
    bundle = Path(bundle)
    manifest = read_json(bundle / "manifest.json")
    draft = (bundle / "draft.json").read_bytes()
    prompt = (bundle / "prompt.txt").read_bytes()
    if digest(draft) != manifest["draft_sha256"] or digest(prompt) != manifest["prompt_sha256"]:
        raise ValueError("plan evidence hash mismatch")
    if (compile_prompt(read_json(bundle / "draft.json")) + "\n").encode("utf-8") != prompt:
        raise ValueError("draft and prompt disagree")
    result: dict[str, Any] = {
        "status": "HOLD", "service": "moss-visual-asset-intelligence",
        "generation_verified": False, "publication_authorized": False,
        "prompt_sha256": manifest["prompt_sha256"], "draft_sha256": manifest["draft_sha256"],
        "evidence_class": "offline_candidate_review", "reasons": [],
    }
    reasons = result["reasons"]
    if image is None:
        reasons.append("no rendered PNG")
    else:
        image = Path(image)
        if image.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("PNG exceeds 100MiB")
        image_data = image.read_bytes()
        result["image_sha256"] = digest(image_data)
        try:
            w, h = png_size(image_data)
            result["image_dimensions"] = {"width": w, "height": h}
            if (w, h) != (manifest["canvas"]["width"], manifest["canvas"]["height"]):
                raise ValueError("canvas size mismatch")
        except ValueError as exc:
            result["status"] = "FAIL"
            reasons.append(str(exc))
        if result["status"] != "FAIL":
            if review is None:
                reasons.append("manual text/composition/style review required")
            else:
                judgment = read_json(Path(review))
                keys = {"image_sha256", "prompt_sha256", "observed_text",
                        "composition_approved", "style_consistent", "reviewer"}
                if not keys.issubset(judgment):
                    reasons.append("missing review fields")
                elif (judgment["image_sha256"] != result["image_sha256"]
                      or judgment["prompt_sha256"] != manifest["prompt_sha256"]):
                    result["status"] = "FAIL"
                    reasons.append("review provenance mismatch")
                elif (judgment["observed_text"] != manifest["expected_visible_text"]
                      or judgment["composition_approved"] is not True
                      or judgment["style_consistent"] is not True
                      or not isinstance(judgment["reviewer"], str)
                      or not judgment["reviewer"].strip()):
                    reasons.append("visual review not approved")
                else:
                    result["status"] = "PASS"
                    result["evidence_class"] = "self_reported_human_review_plus_png_integrity"
                    result["reviewer"] = judgment["reviewer"]
    write_json(bundle / "evaluation.json", result)
    return result
