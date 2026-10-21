"""Synthetic, deterministic MGSF-M1.2 contract demo, NOT a real game run."""
from __future__ import annotations

import argparse
import base64
import json
import struct
import zlib
from pathlib import Path

from mgsf.gua_semantic_bridge import run_gua_probe, verify_gua_evidence


def png(red: int) -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + name + payload
                + struct.pack(">I", zlib.crc32(name + payload) & 0xffffffff))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(bytes((0, red, 25, 100)))) +
            chunk(b"IEND", b""))


class SyntheticGua:
    def __init__(self) -> None:
        self.clicked = False

    def call(self, name: str, arguments=None):
        if name == "get_ui_tree":
            return {"sessionEpoch": 10, "frameSequence": 2 if self.clicked else 1,
                    "screen": "mock", "nodes": [
                        {"id": "Start", "role": "button", "visible": not self.clicked},
                        {"id": "Gameplay", "role": "label", "visible": self.clicked},
                    ]}
        if name == "get_world_object_tree":
            return {"objects": [{"id": "slime", "kind": "enemy", "state": {"hp": 2}}]}
        if name == "get_screenshot":
            return {"dataUri": "data:image/png;base64," +
                    base64.b64encode(png(220 if self.clicked else 5)).decode("ascii")}
        if name == "click_node":
            if arguments != {"nodeId": "Start"}:
                raise ValueError("unexpected click")
            self.clicked = True
            return {"ok": True, "requestId": 9,
                    "completion": {"requestId": 9, "succeeded": True}}
        raise ValueError("unexpected tool")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("evidence/gua-mock"))
    args = parser.parse_args()
    result = run_gua_probe(
        "fixtures/gua/mission.json", SyntheticGua(), args.output_root,
        evidence_class="deterministic_mock_gua_mcp",
    )
    verified = verify_gua_evidence(result.root)
    print(json.dumps({"evidence": str(result.root), "status": result.status,
                      "integrity": verified["status"], "promotion": "HOLD",
                      "source": "SYNTHETIC MOCK, NO RUNNING GODOT/UNITY"}, indent=2))
    return 0 if result.status == "HYBRID_EVIDENCE_SUPPORTED" and verified["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
