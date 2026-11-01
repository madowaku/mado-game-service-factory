"""MGSF Sound Identity M0.4: correlate claimed audio events with verified capture IDs.

This module does not record sound, instrument gameplay, or prove audible output.
Imported WAV hashes, capture provenance, trace alignment, and optionally a
separately supplied PCM recording are independently checked. Promotion stays HOLD.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import wave

from .gameplay_capture import load_capture_session
from .sound_runtime import load_verified_audio_map

TRACE_SCHEMA = "mgsf.sound_identity.audio_timeline.v0.4"
MAX_EVENTS = 500
MAX_TRACE = 1_000_000
MAX_WAV = 40 * 1024 * 1024
KINDS = {"start", "switch", "stop"}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class SoundTimelineError(ValueError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_trace(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_TRACE:
        raise SoundTimelineError("missing, symlinked, or oversized audio trace")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SoundTimelineError("invalid audio trace JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema") != TRACE_SCHEMA:
        raise SoundTimelineError("invalid audio trace schema")
    if raw.get("clock") != "capture_timeline_ms":
        raise SoundTimelineError("trace clock must match capture timeline")
    events = raw.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise SoundTimelineError("trace must have 1..500 audio events")
    return raw


def _decode_pcm(raw: bytes, width: int) -> list[float]:
    if width == 1:
        return [(x - 128) / 128 for x in raw]
    scale = float(1 << (width * 8 - 1))
    return [int.from_bytes(raw[i:i + width], "little", signed=True) / scale
            for i in range(0, len(raw), width)]


def _recording_windows(path: Path, events: list[dict], recording_start_ms: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_WAV:
        raise SoundTimelineError("missing, symlinked, or oversized PCM recording")
    try:
        with wave.open(str(path), "rb") as audio:
            channels, width, rate = audio.getnchannels(), audio.getsampwidth(), audio.getframerate()
            frames = audio.getnframes()
            if audio.getcomptype() != "NONE" or channels not in (1, 2) or width not in (1, 2, 3) or not 8000 <= rate <= 192000:
                raise SoundTimelineError("recording requires mono/stereo PCM WAV (8/16/24bit)")
            result = []
            for event in events:
                # Heuristic window after event (not an acoustic event detector).
                begin_ms = event["at_ms"] + 60 - recording_start_ms
                end_ms = event["at_ms"] + 200 - recording_start_ms
                start = max(0, int(begin_ms * rate / 1000))
                end = min(frames, int(end_ms * rate / 1000))
                if start >= end or begin_ms < 0:
                    result.append({"event_id": event["event_id"], "window_available": False})
                    continue
                audio.setpos(start)
                values = _decode_pcm(audio.readframes(end - start), width)
                if not values:
                    result.append({"event_id": event["event_id"], "window_available": False})
                    continue
                rms = math.sqrt(sum(v * v for v in values) / len(values))
                peak = max(abs(v) for v in values)
                result.append({"event_id": event["event_id"], "window_available": True,
                               "rms": round(rms, 6), "peak": round(peak, 6),
                               "possible_silence": rms < 0.001,
                               "possible_clipping": peak >= 0.999})
            return {"sha256": _sha(path), "sample_rate": rate, "channels": channels,
                    "bit_depth": width * 8, "duration_ms": int(frames * 1000 / rate),
                    "event_windows": result}
    except (wave.Error, EOFError, OSError) as exc:
        raise SoundTimelineError("recording is not a readable PCM WAV") from exc


def run_sound_timeline(capture_root: str | Path, project: str | Path,
                       trace_path: str | Path, output_root: str | Path,
                       *, recording: str | Path | None = None, fixture: bool = False) -> dict:
    capture_root, project, trace_path = Path(capture_root), Path(project), Path(trace_path)
    output = Path(output_root).absolute()
    if output.resolve().is_relative_to(capture_root.resolve()) or output.resolve().is_relative_to(project.resolve()):
        raise SoundTimelineError("evidence output must be outside capture and Godot projects")
    capture = load_capture_session(capture_root)
    tracks = load_verified_audio_map(project)
    track_hashes = {track["sha256"] for track in tracks}
    raw = _read_trace(trace_path)
    if raw.get("capture_id") != capture["capture_id"] or raw.get("session_id") != capture["session_id"]:
        raise SoundTimelineError("capture/session identity mismatch")
    recorded_from = raw.get("recording_start_ms", 0)
    if type(recorded_from) is not int or recorded_from < 0:
        raise SoundTimelineError("invalid recording clock offset")
    capture_events = {x["event_id"]: x for x in capture["timeline"]}
    seen, last_ms, last_kind, linked = set(), -1, None, []
    for item in raw["events"]:
        if not isinstance(item, dict):
            raise SoundTimelineError("audio event must be an object")
        event_id, at_ms = item.get("event_id"), item.get("at_ms")
        source_id, sha, kind = item.get("capture_event_id"), item.get("track_sha256"), item.get("kind")
        if not isinstance(event_id, str) or not event_id or event_id in seen:
            raise SoundTimelineError("invalid or duplicate audio event_id")
        seen.add(event_id)
        if type(at_ms) is not int or at_ms < last_ms or at_ms < 0:
            raise SoundTimelineError("audio event clock is invalid or not monotonic")
        last_ms = at_ms
        if kind not in KINDS:
            raise SoundTimelineError("invalid audio event kind")
        if kind == "stop":
            if last_kind not in {"start", "switch"}:
                raise SoundTimelineError("stop without active audio")
        elif kind == "start":
            if last_kind in {"start", "switch"}:
                raise SoundTimelineError("start while already active; use switch")
        elif last_kind not in {"start", "switch"}:
            raise SoundTimelineError("switch without active audio")
        if not isinstance(sha, str) or not HASH_RE.fullmatch(sha) or sha not in track_hashes:
            raise SoundTimelineError("event references unknown WAV SHA-256")
        if not isinstance(source_id, str) or source_id not in capture_events:
            raise SoundTimelineError("event references unknown capture event")
        source = capture_events[source_id]
        delay = at_ms - source["at_ms"]
        if delay < 0 or delay > 250:
            raise SoundTimelineError("event timestamp exceeds 0..250ms correlation window")
        linked.append({"event_id": event_id, "kind": kind, "at_ms": at_ms,
                       "capture_event_id": source_id, "capture_at_ms": source["at_ms"],
                       "reported_delta_ms": delay, "track_sha256": sha})
        last_kind = kind
    recording_info = None
    flags = []
    if recording is not None:
        recording_info = _recording_windows(Path(recording), raw["events"], recorded_from)
        for item in recording_info["event_windows"]:
            if item.get("window_available") is False:
                flags.append("recording_window_out_of_range")
            if item.get("possible_silence"):
                flags.append("possible_silence_near_audio_event")
            if item.get("possible_clipping"):
                flags.append("possible_clipping_near_audio_event")
    else:
        flags.append("no_recorded_audio")
    if capture["source"].get("evidence_class") != "recorded_gameplay_capture":
        flags.append("capture_not_direct_gameplay")
    if fixture:
        flags.append("synthetic_fixture")
    report = {
        "schema": "mgsf.sound_identity.timeline_eval.v0.4",
        "technical_status": "REVIEW" if flags else "PASS",
        "promotion_gate": "HOLD",
        "capture_id": capture["capture_id"], "session_id": capture["session_id"],
        "capture_evidence_class": capture["source"].get("evidence_class"),
        "audio_evidence_class": "supplied_pcm_recording_unverified_source" if recording_info else "event_trace_only",
        "clock_evidence": "declared_shared_clock_not_independently_synchronized",
        "fixture": fixture,
        "event_count": len(linked),
        "reported_event_delay_max_ms": max(x["reported_delta_ms"] for x in linked),
        "recording": recording_info,
        "flags": sorted(set(flags)),
        "sha256": {"trace": _sha(trace_path),
                   "capture_manifest": _sha(capture_root / "capture.json"),
                   "capture_timeline": _sha(capture_root / "timeline.jsonl")},
        "limits": ["Audio event timestamps are instrumentation claims, not measured audio latency",
                   "A supplied recording does not prove its source, driver, or synchronization",
                   "RMS/peak windows are rough heuristics, not proof of sound identity or loop quality",
                   "No synthesis, recording, scene rewrite, or production promotion performed"],
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "event-links.json", {"schema": TRACE_SCHEMA, "linked_events": linked})
    _write(output / "evaluation.json", report)
    return report
