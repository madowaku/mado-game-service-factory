"""Reproducible synthetic PCM fixture; never genuine Godot/OS acoustic evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import wave

from mgsf.sound_experience import run_sound_experience


def main() -> int:
    root = Path("ci-evidence/sound-experience-fixture").resolve()
    inputs = root / "synthetic-input"
    inputs.mkdir(parents=True, exist_ok=True)
    audio = inputs / "master-bus.wav"
    rate, length = 16000, 32000
    with wave.open(str(audio), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"".join(
            (int(9000 * math.sin(2 * math.pi * 240 * i / rate)) if i < rate else
             int(9000 * math.sin(2 * math.pi * 320 * i / rate))).to_bytes(2, "little", signed=True) * 2
            for i in range(length)
        ))
    manifest = inputs / "capture-manifest.json"
    manifest.write_text(json.dumps({
        "schema": "mgsf.sound_identity.capture_manifest.v0.6",
        "origin": "synthetic_fixture", "audio_driver": "Dummy", "consent": True,
        "sample_rate": rate, "channels": 2, "sample_count": length,
        "capture_started_ticks_usec": 1_000_000, "capture_ended_ticks_usec": 3_000_000,
        "discarded_frames": 0, "recording_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "markers": [{"marker_id": "start-1", "kind": "start", "ticks_usec": 1_200_000},
                    {"marker_id": "switch-1", "kind": "switch", "ticks_usec": 2_000_000},
                    {"marker_id": "stop-1", "kind": "stop", "ticks_usec": 2_800_000}],
    }, indent=2) + "\n", encoding="utf-8")
    report = run_sound_experience(manifest, audio, root / "evaluation", fixture=True)
    if (report["promotion_gate"] != "HOLD" or report["actual_speaker_output_verified"]
        or report["audio"]["sample_count"] != length or report["marker_count"] != 3
        or "synthetic_fixture_not_real_game_audio" not in report["flags"]):
        raise RuntimeError("synthetic M0.6 contract broken")
    print("MGSF_SOUND_EXPERIENCE_FIXTURE_OK markers=3 actual_speaker_output=false promotion=HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
