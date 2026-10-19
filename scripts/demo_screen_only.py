"""Deterministic contract demonstration, NOT a captured game or AI playtest."""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

from mgsf.screen_only_playtest import run_screen_playtest, verify_screen_evidence


def _png(r: int) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(
            ">I", zlib.crc32(name + data) & 0xffffffff
        )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes((0, r, 10, 20))))
        + chunk(b"IEND", b"")
    )


class MockScreenPort:
    def __init__(self):
        self.frame = _png(25)

    def capture(self):
        return self.frame

    def press(self, button, duration_ms):
        if button == "B":
            self.frame = _png(200)


class MockPolicy:
    def choose(self, goal, frame, history, *, rethink, evidence_needed):
        return ("B" if rethink else "A"), 100


class MockJudge:
    def assess(self, goal, before, after):
        return {
            "verdict": "PASS" if before != after else "INSUFFICIENT",
            "reason": "Mock-only image delta; not proof of game progress",
            "visible_before": True,
            "visible_after": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("evidence/demo-screen-only"))
    args = parser.parse_args()
    result = run_screen_playtest(
        "fixtures/screen-only/mission.json", MockScreenPort(), MockPolicy(),
        MockJudge(), args.output_root, policy_id="demo-policy",
        judge_id="demo-judge", evidence_class="deterministic_mock_screen_fixture",
    )
    audit = verify_screen_evidence(result.root)
    print(json.dumps({"bundle": str(result.root), "loop": result.status,
                      "rethink_count": result.rethink_count, "audit": audit["status"],
                      "promotion": result.promotion_status}, indent=2))
    return 0 if result.status == "SCREEN_EVIDENCE_SUPPORTED" and result.rethink_count == 1 and audit["status"] == "PASS" and result.promotion_status == "HOLD" else 1


if __name__ == "__main__":
    raise SystemExit(main())
