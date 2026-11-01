"""Real Sound Experience M0.6: integrity-check captured PCM and claimed in-game markers.

The supplied manifest and samples are user/engine-provided evidence, not trusted
device attestation. The tool never records or uploads audio and NEVER promotes.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import wave

SCHEMA = "mgsf.sound_identity.capture_manifest.v0.6"
EVAL_SCHEMA = "mgsf.sound_identity.experience_eval.v0.6"
MAX_AUDIO = 48 * 1024 * 1024
MAX_MANIFEST = 128 * 1024
DRIVERS_FORBIDDEN = {"Dummy", "dummy", "None", ""}
ORIGINS = {"godot_master_bus_audioeffectcapture", "external_loopback", "synthetic_fixture"}
MARKER_KINDS = {"start", "switch", "stop", "loop", "input"}


class SoundExperienceError(ValueError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_MANIFEST:
        raise SoundExperienceError("missing, symlinked or oversized capture manifest")
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SoundExperienceError("invalid capture JSON") from exc
    if not isinstance(info, dict) or info.get("schema") != SCHEMA:
        raise SoundExperienceError("wrong capture manifest schema")
    return info


def _metric_wav(path: Path, markers: list[dict], capture_started: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_AUDIO:
        raise SoundExperienceError("missing, symlinked or oversized recorded WAV")
    try:
        with wave.open(str(path), "rb") as audio:
            channels, width, rate, frames = (audio.getnchannels(), audio.getsampwidth(),
                                             audio.getframerate(), audio.getnframes())
            if audio.getcomptype() != "NONE" or width != 2 or channels not in (1, 2) or not 8000 <= rate <= 96000:
                raise SoundExperienceError("capture must be mono/stereo PCM16 8..96kHz")
            if not 1 <= frames <= rate * 90:
                raise SoundExperienceError("capture must have 1..90 seconds of audio")
            block_frames = max(1, rate // 20)
            windows, total, clipped, square, longest_silent, silent_run = [], 0, 0, 0.0, 0, 0
            prev_sample, max_adjacent_jump = None, 0.0
            while total < frames:
                take = min(block_frames, frames - total)
                raw = audio.readframes(take)
                if len(raw) != take * channels * width:
                    raise SoundExperienceError("truncated PCM recording")
                values = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32768
                          for i in range(0, len(raw), 2)]
                peak = max(abs(x) for x in values)
                rms = math.sqrt(sum(v*v for v in values) / len(values))
                windows.append({"start_ms": round(total * 1000 / rate, 2),
                                "duration_ms": round(take * 1000 / rate, 2),
                                "rms": round(rms, 6), "peak": round(peak, 6)})
                if rms < 0.001:
                    silent_run += take
                    longest_silent = max(longest_silent, silent_run)
                else:
                    silent_run = 0
                for j in range(0, len(values), channels):
                    # Adjacent comparisons within same channel only; mono-downmix is a proxy.
                    value = sum(values[j:j + channels]) / channels
                    if prev_sample is not None:
                        max_adjacent_jump = max(max_adjacent_jump, abs(value - prev_sample))
                    prev_sample = value
                clipped += sum(abs(v) >= 0.999 for v in values)
                square += sum(v*v for v in values)
                total += take
            marker_windows = []
            for marker in markers:
                offset = (marker["ticks_usec"] - capture_started) * rate / 1_000_000
                idx = round(offset)
                if idx <= 0 or idx >= frames:
                    marker_windows.append({"marker_id": marker["marker_id"], "in_audio_range": False})
                    continue
                # Compare the immediately adjacent samples, not an inferred actual loop.
                audio.setpos(idx - 1)
                pair = audio.readframes(2)
                if len(pair) != 4 * channels:
                    raise SoundExperienceError("marker PCM sample unavailable")
                left, right = pair[:channels * 2], pair[channels * 2:]
                jump = max(abs(
                    int.from_bytes(left[ch*2:ch*2+2], "little", signed=True) -
                    int.from_bytes(right[ch*2:ch*2+2], "little", signed=True)
                ) / 32768 for ch in range(channels))
                marker_windows.append({"marker_id": marker["marker_id"], "kind": marker["kind"],
                                       "in_audio_range": True, "boundary_jump": round(jump, 6)})
    except (OSError, EOFError, wave.Error) as exc:
        raise SoundExperienceError("invalid/truncated PCM WAV") from exc
    return {"channels": channels, "sample_rate": rate, "sample_count": frames,
            "duration_ms": round(frames * 1000 / rate, 3), "rms": round(math.sqrt(square / (frames * channels)), 6),
            "clipped_sample_ratio": round(clipped / (frames * channels), 8),
            "max_adjacent_mono_jump": round(max_adjacent_jump, 6),
            "longest_low_energy_ms": round(longest_silent * 1000 / rate, 2),
            "windows": windows[:1800], "marker_windows": marker_windows, "sha256": _sha(path)}


def run_sound_experience(manifest: str | Path, recording: str | Path, output: str | Path,
                         *, fixture: bool = False) -> dict:
    manifest, recording, output = Path(manifest), Path(recording), Path(output).absolute()
    if output.resolve().is_relative_to(manifest.parent.resolve()) or output.resolve().is_relative_to(recording.parent.resolve()):
        raise SoundExperienceError("output must be outside input directories")
    data = _json(manifest)
    required = ("sample_rate", "channels", "sample_count", "capture_started_ticks_usec",
                "capture_ended_ticks_usec", "discarded_frames")
    for key in required:
        if type(data.get(key)) is not int or data[key] < 0:
            raise SoundExperienceError("invalid capture metadata integer: " + key)
    origin = data.get("origin")
    driver = data.get("audio_driver")
    if origin not in ORIGINS or not isinstance(driver, str) or len(driver) > 64:
        raise SoundExperienceError("invalid source origin or audio driver")
    if data["capture_ended_ticks_usec"] <= data["capture_started_ticks_usec"]:
        raise SoundExperienceError("invalid monotonic capture clock range")
    if data.get("recording_sha256") is None or not isinstance(data["recording_sha256"], str):
        raise SoundExperienceError("recording SHA-256 required")
    if recording.is_symlink() or not recording.is_file() or not 0 < recording.stat().st_size <= MAX_AUDIO:
        raise SoundExperienceError("missing, symlinked or oversized recorded WAV")
    if data["recording_sha256"] != _sha(recording):
        raise SoundExperienceError("recorded audio hash mismatch")
    if data.get("consent") is not True:
        raise SoundExperienceError("explicit user recording consent must be recorded")
    if origin == "synthetic_fixture" and not fixture:
        raise SoundExperienceError("synthetic capture requires --fixture")
    markers = data.get("markers", [])
    if not isinstance(markers, list) or len(markers) > 500:
        raise SoundExperienceError("invalid audio marker array")
    last_ticks, ids = -1, set()
    for marker in markers:
        if not isinstance(marker, dict) or not isinstance(marker.get("marker_id"), str) or not marker["marker_id"] or marker["marker_id"] in ids:
            raise SoundExperienceError("duplicate/invalid marker id")
        ids.add(marker["marker_id"])
        ticks = marker.get("ticks_usec")
        if type(ticks) is not int or ticks < last_ticks or ticks < data["capture_started_ticks_usec"] or ticks > data["capture_ended_ticks_usec"]:
            raise SoundExperienceError("invalid marker monotonic clock")
        if marker.get("kind") not in MARKER_KINDS:
            raise SoundExperienceError("invalid marker kind")
        last_ticks = ticks
    wav = _metric_wav(recording, markers, data["capture_started_ticks_usec"])
    for key in ("sample_rate", "channels", "sample_count"):
        if data[key] != wav[key]:
            raise SoundExperienceError("capture metadata does not match PCM WAV: " + key)
    declared_ms = (data["capture_ended_ticks_usec"] - data["capture_started_ticks_usec"]) / 1000
    drift_ms = round(wav["duration_ms"] - declared_ms, 3)
    flags = []
    if abs(drift_ms) > 100:
        flags.append("capture_clock_duration_mismatch")
    if wav["longest_low_energy_ms"] > 200:
        flags.append("long_silence_in_recording_review")
    if wav["clipped_sample_ratio"] > 0.001:
        flags.append("possible_clipping_in_capture")
    if any(m.get("kind") == "loop" and m.get("boundary_jump", 0) > 0.08 for m in wav["marker_windows"]):
        flags.append("possible_loop_transition_click")
    if data["discarded_frames"] > 0:
        flags.append("audio_capture_ring_buffer_overflow")
    if origin == "external_loopback":
        flags.append("external_loopback_provenance_unverified")
    if driver in DRIVERS_FORBIDDEN:
        flags.append("dummy_audio_driver_not_real_output")
    if fixture:
        flags.append("synthetic_fixture_not_real_game_audio")
    # PASS here is artifact integrity only. No objective listening judgment exists.
    integrity = "REVIEW" if flags else "PASS"
    result = {"schema": EVAL_SCHEMA, "integrity_status": integrity, "promotion_gate": "HOLD",
              "evidence_class": "synthetic_pcm_capture_fixture" if fixture else "self_reported_audio_capture",
              "actual_speaker_output_verified": False,
              "origin_claim": origin, "driver_claim": driver, "capture_consent_claim": True,
              "audio": wav, "marker_count": len(markers),
              "capture_duration_drift_ms": drift_ms, "flags": sorted(set(flags)),
              "input_sha256": {"manifest": _sha(manifest), "recording": wav["sha256"]},
              "limits": ["Manifest and monotonic timestamps are assertions from the capture tool, not hardware attestation.",
                         "Master-bus capture samples are engine-mix data, not independently verified speaker output.",
                         "Markers estimate location from engine clock; no measured input-to-audible latency.",
                         "Adjacent sample jumps and RMS are heuristics, not verified audible loop or player pleasure.",
                         "Synthetic fixture, unreviewed real-project integration and licensing cannot promote."]}
    output.mkdir(parents=True, exist_ok=True)
    target = output / "evaluation.json"
    if target.is_symlink():
        raise SoundExperienceError("evaluation symlink forbidden")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
