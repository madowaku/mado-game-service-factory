"""Generate a local, dependency-free creative QA contract fixture.

This makes a valid tiny GLB triangle and two synthetic PNG frames. It does
NOT reconstruct an image or prove a real Three.js / Godot render.
"""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path


def _png(rgb: tuple[int, int, int], width: int = 128, height: int = 128) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    row = b"\0" + bytes(rgb) * width
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height))
            + chunk(b"IEND", b""))


def _triangle_glb() -> bytes:
    vertices = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    indices = struct.pack("<3H", 0, 1, 2)
    binary = vertices + indices + b"\0\0"
    doc = {
        "asset": {"version": "2.0", "generator": "MGSF deterministic triangle fixture"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(vertices) + len(indices)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(vertices), "target": 34962},
            {"buffer": 0, "byteOffset": len(vertices), "byteLength": len(indices), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
             "min": [0, 0, 0], "max": [1, 1, 0]},
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
    }
    data = json.dumps(doc, separators=(",", ":"), sort_keys=True).encode("utf-8")
    data += b" " * ((-len(data)) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(data) + 8 + len(binary))
            + struct.pack("<I4s", len(data), b"JSON") + data
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def make_fixture(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=False)
    (root / "frames").mkdir()
    (root / "reference.png").write_bytes(_png((240, 200, 60)))
    (root / "frames" / "000.png").write_bytes(_png((35, 100, 200)))
    (root / "frames" / "001.png").write_bytes(_png((50, 140, 230)))
    (root / "scene.glb").write_bytes(_triangle_glb())
    (root / "scene.js").write_text(
        "// Synthetic reference fixture only; no executable upstream imported.\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "run_id": "fixture-triangle-001",
        "reference_image": "reference.png",
        "scene": "scene.glb",
        "source_code": "scene.js",
        "frames": ["frames/000.png", "frames/001.png"],
        "source": {"generator": "mgsf-stdlib-fixture",
                   "evidence_class": "deterministic_fixture"},
        "rights": {"license": "unknown", "reviewed": False},
    }
    (root / "run.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(make_fixture(args.root))
