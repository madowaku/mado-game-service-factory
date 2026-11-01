"""Produce reproducible M0.4 fixture: linked gameplay/audio trace and synthetic PCM.

A reconstruction fixture is NOT direct gameplay, and the rendered tone is NOT a
recording of Godot output. All promotion gates stay HOLD.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import wave

from mgsf.sound_timeline import run_sound_timeline


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("ci-evidence/sound-timeline-fixture"))
    args = ap.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    capture = Path("fixtures/gameplay-capture/vertical-slice-reconstruction").resolve()
    tracks = json.loads((args.project / "audio/mgsf_sound_identity/sound_map.json").read_text())["tracks"]
    if len(tracks) != 2 or tracks[0]["sha256"] == tracks[1]["sha256"]:
        raise RuntimeError("M0.4 fixture requires two distinct audio hashes")
    a, b = [t["sha256"] for t in tracks]
    trace = {"schema": "mgsf.sound_identity.audio_timeline.v0.4",
             "capture_id": "vertical-slice-c6-reconstruction", "session_id": "capture-001",
             "clock": "capture_timeline_ms", "recording_start_ms": 0,
             "events": [
                 {"event_id": "a-start", "kind": "start", "at_ms": 1420, "capture_event_id": "capture-event-002", "track_sha256": a},
                 {"event_id": "a-switch", "kind": "switch", "at_ms": 1615, "capture_event_id": "capture-event-003", "track_sha256": b},
                 {"event_id": "b-stop", "kind": "stop", "at_ms": 1825, "capture_event_id": "capture-event-004", "track_sha256": b},
             ]}
    trace_path = root / "synthetic-audio-timeline.json"
    trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    wav_path = root / "synthetic-tone-NOT-recorded-from-godot.wav"
    with wave.open(str(wav_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(
            int(9000 * math.sin(2 * math.pi * 210 * i / 16000)).to_bytes(2, "little", signed=True)
            for i in range(16000 * 3)
        ))
    report = run_sound_timeline(capture, args.project, trace_path, root / "evaluation",
                                recording=wav_path, fixture=True)
    if report["promotion_gate"] != "HOLD" or report["technical_status"] != "REVIEW":
        raise RuntimeError("synthetic evidence must remain REVIEW / HOLD")
    if report["event_count"] != 3 or report["reported_event_delay_max_ms"] != 25:
        raise RuntimeError("fixture event timeline join is wrong")
    if report["capture_evidence_class"] != "reconstructed_from_verified_state":
        raise RuntimeError("reconstructed screenshots must not masquerade as live media")
    print("MGSF_SOUND_TIMELINE_FIXTURE_OK events=3 technical=REVIEW promotion=HOLD audio=synthetic_not_recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
