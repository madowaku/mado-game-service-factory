"""Reproducible synthetic-WAV + real-Godot CI dogfood (not audible evidence).

Outputs source ZIP, Godot fixture project, hashes, engine state, and evaluation
under one CI evidence directory. Never marks production promotion PASS.
"""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path
import wave
import zipfile

from mgsf.sound_identity import run_sound_identity
from mgsf.sound_runtime import run_sound_runtime


def _tone(hz: float) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(16000)
        sound.writeframes(b"".join(
            int(8000 * math.sin(2 * math.pi * hz * j / 16000)).to_bytes(2, "little", signed=True)
            for j in range(8000)
        ))
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True)
    parser.add_argument("--out", type=Path, default=Path("ci-evidence/sound-runtime-fixture"))
    args = parser.parse_args()

    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    project = root / "project"
    project.mkdir(exist_ok=True)
    (project / "project.godot").write_text('[application]\nconfig/name="MGSF Sound Identity Synthetic CI"\n', encoding="utf-8")
    archive = root / "synthetic-export.zip"
    with zipfile.ZipFile(archive, "w") as f:
        f.writestr("title.wav", _tone(200))
        f.writestr("battle.wav", _tone(320))
    mapping = root / "scene-map.json"
    mapping.write_text(json.dumps({
        "schema": "mgsf.sound_identity.scene_map.v0.2",
        "scenes": {},
        "loops": ["title.wav"],
    }, indent=2) + "\n", encoding="utf-8")

    stage = run_sound_identity(archive, project, root / "m02-import.json", mapping, apply=True)
    if stage["technical_status"] != "PASS" or not stage["applied"]:
        raise RuntimeError("M0.2 synthetic fixture import failed")
    probe = run_sound_runtime(project, args.godot, root / "runtime", fixture=True)
    if probe["technical_status"] != "PASS" or probe["promotion_gate"] != "HOLD" or probe["observed_audio"]:
        raise RuntimeError("M0.3 engine state fixture failed or promotion contract violated")
    if probe["track_count"] != 2:
        raise RuntimeError("M0.3 two-track switch contract failed")
    print(f"MGSF_SOUND_CI_ENGINE_STATE_OK evidence={root} tracks=2 promotion=HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
