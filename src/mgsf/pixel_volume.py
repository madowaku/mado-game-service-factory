"""Deterministic voxel-primitives -> horizontal sprite-stack PNG (no third-party deps).

This is a fixture/asset preparation service, not proof of engine rendering.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib
from pathlib import Path
from typing import Any

MAX_PIXELS = 4_000_000


def _color(value: str) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None:
        raise ValueError("shape.color must be #RRGGBB")
    return bytes.fromhex(value[1:]) + b"\xff"


def _dimensions(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3 or any(type(n) is not int or not 1 <= n <= 64 for n in value):
        raise ValueError("size must contain three integers in 1..64: [width, depth, height]")
    w, d, h = value
    if w * d * h > MAX_PIXELS:
        raise ValueError("sprite sheet exceeds pixel budget")
    return w, d, h


def _png_rgba(width: int, height: int, pixels: bytes) -> bytes:
    if len(pixels) != width * height * 4:
        raise ValueError("incorrect RGBA buffer size")

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    stride = width * 4
    raw = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, level=9)) + chunk(b"IEND", b""))


def build_sheet(spec: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    if spec.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    w, d, h = _dimensions(spec.get("size"))
    shapes = spec.get("shapes")
    if not isinstance(shapes, list) or not 1 <= len(shapes) <= 128:
        raise ValueError("shapes must be a nonempty list of at most 128 shapes")
    voxels = bytearray(w * d * h * 4)
    for shape in shapes:
        if not isinstance(shape, dict):
            raise ValueError("every shape must be an object")
        rgba = _color(shape.get("color"))
        kind = shape.get("kind")
        if kind == "box":
            lo, hi = shape.get("min"), shape.get("max")
            if not (isinstance(lo, list) and isinstance(hi, list) and len(lo) == len(hi) == 3
                    and all(type(a) is int and type(b) is int and 0 <= a < b <= limit
                            for a, b, limit in zip(lo, hi, (w, d, h)))):
                raise ValueError("box min/max must be integer coordinates within size (max exclusive)")
            coords = ((x, y, z) for z in range(lo[2], hi[2])
                      for y in range(lo[1], hi[1]) for x in range(lo[0], hi[0]))
        elif kind == "ellipsoid":
            center, radius = shape.get("center"), shape.get("radius")
            if not (isinstance(center, list) and isinstance(radius, list)
                    and len(center) == len(radius) == 3
                    and all(type(n) in (int, float) for n in center + radius)
                    and all(n > 0 for n in radius)):
                raise ValueError("ellipsoid center/radius must be numeric, radius positive")
            coords = ((x, y, z) for z in range(h) for y in range(d) for x in range(w)
                      if sum(((v + 0.5 - c) / r) ** 2 for v, c, r in zip((x, y, z), center, radius)) <= 1.0)
        else:
            raise ValueError("shape.kind must be box or ellipsoid")
        for x, y, z in coords:
            i = ((z * d + y) * w + x) * 4
            voxels[i:i + 4] = rgba
    # Each slice is a top-down w x d image, ground slice on the LEFT.
    result = bytearray(len(voxels))
    for z in range(h):
        for y in range(d):
            src = ((z * d + y) * w) * 4
            dst = (y * (w * h) + z * w) * 4
            result[dst:dst + w * 4] = voxels[src:src + w * 4]
    png = _png_rgba(w * h, d, bytes(result))
    occupancy = sum(voxels[i] != 0 for i in range(3, len(voxels), 4))
    return png, {"width": w, "depth": d, "slices": h, "sheet_width": w * h,
                 "sheet_height": d, "opaque_voxels": occupancy,
                 "png_sha256": hashlib.sha256(png).hexdigest()}


def build_fixture(source: Path, output_root: Path) -> Path:
    source_bytes = source.read_bytes()
    spec = json.loads(source_bytes)
    if not isinstance(spec, dict):
        raise ValueError("spec root must be an object")
    png, info = build_sheet(spec)
    name = spec.get("name")
    if not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,47}", name) is None:
        raise ValueError("name must be a lowercase, hyphenated asset ID")
    output_root.mkdir(parents=True, exist_ok=True)
    png_path = output_root / (name + ".png")
    manifest_path = output_root / (name + ".json")
    png_path.write_bytes(png)
    manifest = {"schema_version": 1, "asset": name, "format": "horizontal-slice-sheet",
                "order": "bottom-left-to-top-right", "source_kind": "procedural_voxel_fixture",
                "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "evidence_class": "synthetic_asset_fixture", "engine_render_verified": False,
                "promotion_gate": "HOLD", **info}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build a deterministic sprite stacking slice sheet")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    print(build_fixture(args.fixture, args.output_root))
