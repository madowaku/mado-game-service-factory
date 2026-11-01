"""Reproducible synthetic Sound Director CI fixture.

Generated MIDI is test data, not an AMIX export, performance, or human review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgsf.sound_director import run_sound_director


def vlq(n: int) -> bytes:
    parts = [n & 127]
    n >>= 7
    while n:
        parts.insert(0, 0x80 | (n & 127))
        n >>= 7
    return bytes(parts)


def midi_file(notes: list[int]) -> bytes:
    events = bytearray()
    for note in notes:
        events.extend(b"\x00\x90" + bytes([note, 100]))
        events.extend(vlq(240) + b"\x80" + bytes([note, 0]))
    events.extend(b"\x00\xff\x2f\x00")
    return (b"MThd" + (6).to_bytes(4, "big") + b"\x00\x00\x00\x01\x01\xe0" +
            b"MTrk" + len(events).to_bytes(4, "big") + events)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("ci-evidence/sound-director-fixture"))
    args = ap.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    tracks = json.loads((args.project / "audio/mgsf_sound_identity/sound_map.json").read_text())["tracks"]
    by_source = {item["source"]: item for item in tracks}
    if set(by_source) != {"title.wav", "battle.wav"}:
        raise RuntimeError("unexpected fixture track map")
    (root / "title.mid").write_bytes(midi_file([60, 62, 64, 65, 67, 69, 71]))
    (root / "battle.mid").write_bytes(midi_file([72, 74, 76, 77, 79, 81, 83]))
    brief = {"schema": "mgsf.sound_identity.director_brief.v0.5",
             "tracks": [
                {"role": "title", "destination": by_source["title.wav"]["destination"],
                 "scene": "res://title.tscn", "midi": "title.mid"},
                {"role": "battle", "destination": by_source["battle.wav"]["destination"],
                 "scene": "res://battle.tscn", "midi": "battle.mid"}]}
    bpath = root / "brief.json"
    bpath.write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")
    result = run_sound_director(args.project, bpath, root / "evidence", fixture=True)
    if (result["track_count"] != 2 or result["promotion_gate"] != "HOLD" or
        result["motif_comparisons"][0]["pattern_overlap"] != 1.0 or
        result["human_review"]["provided"]):
        raise RuntimeError("director fixture metrics or safety contract failed")
    print("MGSF_SOUND_DIRECTOR_FIXTURE_OK tracks=2 motif_overlap=1.0 promotion=HOLD review=unfilled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
