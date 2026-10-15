"""MGSF-M0.9.2: independently decode video frames and compare to Godot state.

Visual measurements come from FFmpeg-decoded RGB pixels, never from the
agent's claimed positions. This is a constrained color-tracker adapter, not
a general computer-vision detector.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
import json
import re
import subprocess
from typing import Any

from .godogen_adapter import _sha, _verify_video
from .godogen_state_verification import StateVerificationError, _within, _write, load_contract

MAX_PIXELS = 1920 * 1080
MAX_PROBES = 12


@dataclass(frozen=True)
class FrameProofVerdict:
    root: Path
    status: str
    matched: int
    total: int


def load_frame_probe(mission: dict[str, Any]) -> dict[str, Any]:
    probe = mission.get("frame_probe")
    if not isinstance(probe, dict):
        raise StateVerificationError("mission requires frame_probe")
    expected = {"fps", "world_width", "world_height", "color_rgb",
                "color_tolerance", "min_pixels", "max_pixels",
                "position_tolerance_px", "ticks"}
    if set(probe) != expected:
        raise StateVerificationError("frame_probe keys must match the color tracker contract")
    def finite_number(key: str, lo: float, hi: float) -> float:
        value = probe[key]
        if type(value) not in (int, float) or not isfinite(value) or not lo <= value <= hi:
            raise StateVerificationError(f"invalid frame_probe {key}")
        return float(value)
    finite_number("fps", 1, 120)
    finite_number("world_width", 100, 4096)
    finite_number("world_height", 100, 4096)
    finite_number("color_tolerance", 1, 80)
    finite_number("position_tolerance_px", 1, 60)
    min_pixels = finite_number("min_pixels", 10, 50000)
    max_pixels = finite_number("max_pixels", min_pixels, 150000)
    for name in ("min_pixels", "max_pixels"):
        if type(probe[name]) is not int:
            raise StateVerificationError(f"{name} must be integer")
    rgb = probe["color_rgb"]
    if not isinstance(rgb, list) or len(rgb) != 3 or any(
        type(v) is not int or not 0 <= v <= 255 for v in rgb
    ):
        raise StateVerificationError("color_rgb must be three integers from 0 to 255")
    ticks = probe["ticks"]
    if not isinstance(ticks, list) or not 3 <= len(ticks) <= MAX_PROBES or any(
        type(t) is not int or not 1 <= t <= 3600 for t in ticks
    ) or ticks != sorted(set(ticks)):
        raise StateVerificationError("frame_probe ticks must be 3-12 unique ascending integers")
    return probe


def rgb_centroid(raw: bytes, width: int, height: int, rgb: tuple[int, int, int],
                 tolerance: int, min_pixels: int, max_pixels: int) -> tuple[float, float, int] | None:
    """Scan full frame; don't crop around the *claimed* player position."""
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS or len(raw) != width * height * 3:
        return None
    count = sx = sy = 0
    view = memoryview(raw)
    for offset in range(0, len(view), 3):
        if all(abs(view[offset + k] - rgb[k]) <= tolerance for k in range(3)):
            p = offset // 3
            sx += p % width
            sy += p // width
            count += 1
    if not min_pixels <= count <= max_pixels:
        return None
    return (sx / count, sy / count, count)


def _decode_rgb(ffmpeg: str, video: Path, tick: int, fps: float, width: int, height: int) -> bytes:
    # Input only influences a bounded argv list; never invoke a shell.
    # Seek to deterministic capture time and decode the corresponding frame.
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss",
            f"{tick / fps:.6f}", "-i", str(video), "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    try:
        result = subprocess.run(args, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StateVerificationError(f"FFmpeg frame decode unavailable: {type(exc).__name__}") from exc
    if result.returncode != 0 or len(result.stdout) != width * height * 3:
        raise StateVerificationError("FFmpeg could not decode an exact RGB video frame")
    return result.stdout


def verify_frame_proof(
    project: str | Path,
    mission_path: str | Path,
    *,
    trace_path: str,
    video_path: str,
    state_evidence_path: str | Path,
    output_root: str | Path,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    fixture: bool = False,
) -> FrameProofVerdict:
    project = Path(project).resolve()
    mission = load_contract(mission_path)
    probe = load_frame_probe(mission)
    trace = _within(project, trace_path, ".json")
    video = _within(project, video_path, ".mp4")
    state_path = Path(state_evidence_path).resolve()
    if not state_path.is_file() or state_path.is_symlink():
        raise StateVerificationError("state evaluation file not found or symlinked")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    data = json.loads(trace.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("mission_id") != mission["mission_id"]:
        raise StateVerificationError("trace mission does not match")
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{7,79}", run_id):
        raise StateVerificationError("invalid frame-proof run_id")
    evidence_valid = (
        isinstance(state, dict)
        and state.get("service") == "godogen-gameplay-state-verification"
        and state.get("mission_id") == mission["mission_id"]
        and state.get("run_id") == run_id
        and state.get("status") == "PASS"
        and state.get("runner_verified") is True
        and state.get("video_verified") is True
        and all(isinstance(c, dict) and c.get("pass") is True
                for c in state.get("checks", []))
        and len(state.get("checks", [])) == len(mission["state_checks"])
        and state.get("state_trace", {}).get("sha256") == _sha(trace)
        and state.get("video", {}).get("sha256") == _sha(video)
        and state.get("runner", {}).get("run_id") == run_id
        and state.get("runner", {}).get("trace_sha256") == _sha(trace)
        and state.get("runner", {}).get("video_sha256") == _sha(video)
    )
    ok_video, meta = _verify_video(video, ffprobe)
    streams = meta.get("streams", []) if isinstance(meta, dict) else []
    stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
    if width * height > MAX_PIXELS:
        raise StateVerificationError("video exceeds bounded frame dimensions")
    by_tick = {item["tick"]: item for item in data.get("samples", [])
               if isinstance(item, dict) and type(item.get("tick")) is int}
    results: list[dict[str, Any]] = []
    can_decode = bool(evidence_valid and ok_video and width > 0 and height > 0)
    for tick in probe["ticks"]:
        sample = by_tick.get(tick)
        observed = None
        color_count = 0
        if can_decode and sample is not None and 0.5 <= tick / probe["fps"] <= float(meta["duration_seconds"]) - 0.1:
            try:
                raw = _decode_rgb(ffmpeg, video, tick, float(probe["fps"]), width, height)
                centroid = rgb_centroid(raw, width, height, tuple(probe["color_rgb"]),
                                        int(probe["color_tolerance"]),
                                        probe["min_pixels"], probe["max_pixels"])
                if centroid is not None:
                    observed, color_count = (centroid[0], centroid[1]), centroid[2]
            except StateVerificationError:
                pass
        expected = None
        delta = None
        match = False
        if sample is not None and isinstance(sample.get("state"), dict):
            pos = sample["state"]
            if all(type(pos.get(k)) in (int, float) and isfinite(pos[k]) for k in ("x", "y")):
                expected = (float(pos["x"]) * width / probe["world_width"],
                            float(pos["y"]) * height / probe["world_height"])
        if observed is not None and expected is not None:
            delta = max(abs(observed[0] - expected[0]), abs(observed[1] - expected[1]))
            match = delta <= probe["position_tolerance_px"]
        results.append({
            "tick": tick, "time_seconds": round(tick / probe["fps"], 4),
            "observed_pixel_center": list(observed) if observed is not None else None,
            "expected_pixel_center": list(expected) if expected is not None else None,
            "pixel_error_max": round(delta, 3) if delta is not None else None,
            "matched_pixels": color_count, "pass": match,
        })
    status = (
        "HOLD" if fixture or not evidence_valid else
        "PASS" if can_decode and all(v["pass"] for v in results) else "ITERATE"
    )
    root = Path(output_root) / mission["mission_id"] / run_id
    _write(root / "frame-proof.json", {
        "schema_version": 1, "service": "godogen-state-to-frame-proof",
        "mission_id": mission["mission_id"], "run_id": run_id,
        "evidence_class": "deterministic_frame_fixture" if fixture else "recorded_gameplay_frame_probe",
        "status": status, "autonomous_status": "HOLD",
        "source_state_evaluation_sha256": _sha(state_path),
        "state_evaluation_verified": bool(evidence_valid),
        "source_trace_sha256": _sha(trace), "source_video_sha256": _sha(video),
        "video_probe": meta, "probe_contract": probe, "checks": results,
        "provenance_note": "Decoded screen pixels compared to same-run telemetry; no claim of autonomous game construction.",
    })
    return FrameProofVerdict(root, status, sum(bool(x["pass"]) for x in results), len(results))
