"""MGSF Sound Director M0.5: deterministic audio identity review assistance.

This is a bounded *heuristic*, not generative music, audio recognition,
psychoacoustic measurement, or a substitute for real gameplay and listening.
No game assets are written. Promotion always stays HOLD.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import wave

from .sound_runtime import load_verified_audio_map

BRIEF_SCHEMA = "mgsf.sound_identity.director_brief.v0.5"
REPORT_SCHEMA = "mgsf.sound_identity.director_eval.v0.5"
REVIEW_SCHEMA = "mgsf.sound_identity.human_review.v0.5"
ROLES = {"title", "menu", "exploration", "puzzle", "battle", "boss", "result", "ending", "ambient"}
SCORES = ("scene_fit", "motif_recognizability", "loop_naturalness", "mix_balance")
MAX_MIDI = 2 * 1024 * 1024
MAX_BRIEF = 128 * 1024
MAX_EVENTS = 20000


class SoundDirectorError(ValueError):
    """Review input or bounded MIDI/WAV data was invalid."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise SoundDirectorError("missing, symlinked or oversized JSON input")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SoundDirectorError("invalid JSON") from exc
    if not isinstance(value, dict):
        raise SoundDirectorError("JSON must be an object")
    return value


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _varlen(data: bytes, pos: int, end: int) -> tuple[int, int]:
    n = 0
    for _ in range(4):
        if pos >= end:
            raise SoundDirectorError("truncated MIDI variable-length number")
        v = data[pos]
        pos += 1
        n = (n << 7) | (v & 127)
        if v < 128:
            return n, pos
    raise SoundDirectorError("MIDI variable-length number exceeds 4 bytes")


def _midi_motifs(path: Path) -> dict:
    """Select densest track/channel melody proxy; 4-note interval patterns.

    This cannot determine melody, harmonies, musical identity, or authorship.
    Format 0/1 PPQ files only. No dependencies, execution or SysEx playback.
    """
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_MIDI:
        raise SoundDirectorError("missing, symlinked or oversized MIDI")
    data = path.read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise SoundDirectorError("invalid MIDI header")
    header_len = int.from_bytes(data[4:8], "big")
    if header_len < 6 or 8 + header_len > len(data):
        raise SoundDirectorError("invalid MIDI header length")
    fmt = int.from_bytes(data[8:10], "big")
    ntracks = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    if fmt not in (0, 1) or not 1 <= ntracks <= 32 or (fmt == 0 and ntracks != 1):
        raise SoundDirectorError("unsupported MIDI format/track count")
    if division & 0x8000 or division == 0:
        raise SoundDirectorError("SMPTE/invalid MIDI timing not supported")
    pos = 8 + header_len
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for track_id in range(ntracks):
        if pos + 8 > len(data) or data[pos:pos + 4] != b"MTrk":
            raise SoundDirectorError("missing MIDI MTrk chunk")
        length = int.from_bytes(data[pos + 4:pos + 8], "big")
        pos += 8
        end = pos + length
        if end > len(data):
            raise SoundDirectorError("truncated MIDI track")
        running = None
        clock = 0
        events = 0
        while pos < end:
            delta, pos = _varlen(data, pos, end)
            clock += delta
            if pos >= end:
                raise SoundDirectorError("truncated MIDI event")
            status = data[pos]
            if status & 0x80:
                pos += 1
                if status < 0xF0:
                    running = status
                else:
                    running = None
            else:
                if running is None:
                    raise SoundDirectorError("running MIDI status without channel event")
                status = running
            events += 1
            if events > MAX_EVENTS:
                raise SoundDirectorError("MIDI track event limit exceeded")
            if status == 0xFF:
                if pos >= end:
                    raise SoundDirectorError("truncated MIDI meta event")
                kind = data[pos]
                pos += 1
                size, pos = _varlen(data, pos, end)
                if pos + size > end:
                    raise SoundDirectorError("truncated MIDI meta payload")
                pos += size
                if kind == 0x2F:
                    if size != 0 or pos != end:
                        raise SoundDirectorError("invalid MIDI end-of-track")
                    break
            elif status in (0xF0, 0xF7):
                size, pos = _varlen(data, pos, end)
                if pos + size > end:
                    raise SoundDirectorError("truncated MIDI sysex payload")
                pos += size
            elif 0x80 <= status <= 0xEF:
                kind = status & 0xF0
                width = 1 if kind in (0xC0, 0xD0) else 2
                if pos + width > end or any(x >= 128 for x in data[pos:pos + width]):
                    raise SoundDirectorError("invalid MIDI channel payload")
                pitch = data[pos]
                velocity = data[pos + 1] if width == 2 else 0
                pos += width
                channel = status & 0x0F
                if kind == 0x90 and velocity > 0 and channel != 9:
                    groups.setdefault((track_id, channel), []).append((clock, pitch))
            else:
                raise SoundDirectorError("unsupported MIDI system event")
        pos = end
    # Deterministic selection, not true polyphonic voice extraction.
    if not groups:
        return {"sha256": _sha(path), "note_onsets": 0, "pattern_count": 0,
                "interval_patterns": [], "selection": "none"}
    selected = sorted(groups.items(), key=lambda item: (-len({t for t, _ in item[1]}),
                                                        -len(item[1]), item[0]))[0]
    onsets: dict[int, int] = {}
    for tick, pitch in selected[1]:
        onsets[tick] = max(pitch, onsets.get(tick, -1))
    sequence = [pitch for _, pitch in sorted(onsets.items())]
    patterns = sorted({tuple(sequence[i + j + 1] - sequence[i + j] for j in range(3))
                       for i in range(len(sequence) - 3)})
    return {"sha256": _sha(path), "note_onsets": len(sequence),
            "pattern_count": len(patterns), "interval_patterns": [list(p) for p in patterns],
            "selection": f"densest_track_channel_{selected[0][0]}_{selected[0][1]}"}


def _safe_midi(brief: Path, name: str) -> Path:
    if not name or "\\" in name or ":" in name:
        raise SoundDirectorError("MIDI reference must be a local relative name")
    rel = PurePosixPath(name)
    if rel.is_absolute() or not rel.parts or any(x in (".", "..") or x.startswith(".") for x in rel.parts):
        raise SoundDirectorError("MIDI traversal/hidden paths forbidden")
    current = brief.parent
    if current.is_symlink():
        raise SoundDirectorError("symlinked brief directory")
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise SoundDirectorError("symlinked MIDI source forbidden")
    target = current
    if target.suffix.lower() not in (".mid", ".midi") or not target.resolve().is_relative_to(brief.parent.resolve()):
        raise SoundDirectorError("invalid MIDI destination")
    return target


def _seam(path: Path) -> dict:
    """Measure final -> initial sample jump for requested loops, no listening claim."""
    try:
        with wave.open(str(path), "rb") as audio:
            ch, width, rate, frames = (audio.getnchannels(), audio.getsampwidth(),
                                       audio.getframerate(), audio.getnframes())
            if audio.getcomptype() != "NONE" or ch not in (1, 2) or width not in (1, 2, 3, 4):
                raise SoundDirectorError("unsupported PCM WAV loop")
            if frames < 4 or rate < 8000 or rate > 192000:
                raise SoundDirectorError("short/invalid PCM WAV loop")
            start = audio.readframes(1)
            audio.setpos(frames - 1)
            tail = audio.readframes(1)
        scale = float(1 << (width * 8 - 1))
        def sample(blob: bytes, channel: int) -> float:
            b = blob[channel * width:(channel + 1) * width]
            if len(b) != width:
                raise SoundDirectorError("truncated PCM WAV")
            return ((b[0] - 128) if width == 1 else int.from_bytes(b, "little", signed=True)) / scale
        jump = max(abs(sample(start, i) - sample(tail, i)) for i in range(ch))
        return {"boundary_sample_jump": round(jump, 6), "unit": "normalized_peak_amplitude",
                "possible_click_risk": jump > 0.08,
                "method": "last_sample_vs_first_sample_only"}
    except (wave.Error, EOFError, OSError) as exc:
        raise SoundDirectorError("invalid PCM WAV seam") from exc


def _review(review: Path | None, required: set[str]) -> dict:
    if review is None:
        return {"provided": False, "covered_tracks": 0, "reviewer_claim": None,
                "source_hash": None, "complete": False}
    payload = _read_json(review, MAX_BRIEF)
    if payload.get("schema") != REVIEW_SCHEMA:
        raise SoundDirectorError("invalid review schema")
    reviewer = payload.get("reviewer")
    if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 100:
        raise SoundDirectorError("reviewer attribution required")
    assessments = payload.get("assessments")
    if not isinstance(assessments, list) or len(assessments) > 12:
        raise SoundDirectorError("invalid review assessments")
    seen = set()
    for item in assessments:
        if not isinstance(item, dict) or not isinstance(item.get("destination"), str) or item["destination"] not in required:
            raise SoundDirectorError("review references unknown destination")
        dest = item["destination"]
        if dest in seen:
            raise SoundDirectorError("duplicate human review destination")
        seen.add(dest)
        for name in SCORES:
            if type(item.get(name)) is not int or not 1 <= item[name] <= 5:
                raise SoundDirectorError("review scores must be integers 1..5")
        if not isinstance(item.get("notes"), str) or len(item["notes"]) > 1000:
            raise SoundDirectorError("review notes are required and limited")
    return {"provided": True, "covered_tracks": len(seen), "reviewer_claim": reviewer.strip(),
            "source_hash": _sha(review), "complete": seen == required,
            "provenance": "unverified_human_review_claim"}


def run_sound_director(project: str | Path, brief: str | Path, output_root: str | Path,
                       *, review: str | Path | None = None, fixture: bool = False) -> dict:
    project, brief, output = Path(project), Path(brief), Path(output_root)
    if output.resolve().is_relative_to(project.resolve()):
        raise SoundDirectorError("output must be outside project")
    imported = load_verified_audio_map(project)
    lookup = {item["destination"]: item for item in imported}
    data = _read_json(brief, MAX_BRIEF)
    if data.get("schema") != BRIEF_SCHEMA or not isinstance(data.get("tracks"), list):
        raise SoundDirectorError("invalid director brief schema")
    entries = data["tracks"]
    if not 1 <= len(entries) <= 12:
        raise SoundDirectorError("director brief must contain 1..12 tracks")
    seen, results, motifs, flags = set(), [], {}, []
    for item in entries:
        if not isinstance(item, dict):
            raise SoundDirectorError("director brief track must be an object")
        dest, role, scene = item.get("destination"), item.get("role"), item.get("scene")
        if not isinstance(dest, str) or dest not in lookup or dest in seen:
            raise SoundDirectorError("unknown or duplicate Godot audio destination")
        seen.add(dest)
        if role not in ROLES:
            raise SoundDirectorError("unknown soundtrack role")
        if not isinstance(scene, str) or not scene.startswith("res://") or not scene.endswith(".tscn"):
            raise SoundDirectorError("scene reference must be a res:// .tscn")
        if any(x in ("", ".", "..") for x in scene[6:].split("/")) or "\\" in scene or ":" in scene[6:]:
            raise SoundDirectorError("invalid scene reference")
        sound = lookup[dest]
        midi_path = item.get("midi")
        midi_info = None
        if midi_path is not None:
            if not isinstance(midi_path, str):
                raise SoundDirectorError("MIDI reference must be a string")
            midi_info = _midi_motifs(_safe_midi(brief, midi_path))
            motifs[dest] = {tuple(x) for x in midi_info.pop("interval_patterns")}
            if midi_info["pattern_count"] == 0:
                flags.append("midi_too_short_for_4_note_motif")
        else:
            flags.append("midi_not_supplied")
        seam = _seam(Path(sound["path"])) if sound["loop_requested"] else None
        if seam and seam["possible_click_risk"]:
            flags.append("possible_loop_boundary_click")
        results.append({"destination": dest, "track_sha256": sound["sha256"],
                        "role": role, "planned_scene": scene, "scene_binding_verified": False,
                        "loop_requested": sound["loop_requested"], "loop_seam_heuristic": seam,
                        "midi": midi_info})
    references = [e for e in results if e["role"] == "title" and e["destination"] in motifs]
    anchor = references[0]["destination"] if references else next(iter(motifs), None)
    comparisons = []
    if anchor:
        base = motifs[anchor]
        for entry in results:
            dest = entry["destination"]
            if dest == anchor:
                continue
            if dest not in motifs or not base or not motifs[dest]:
                comparisons.append({"reference": anchor, "target": dest, "pattern_overlap": None,
                                    "interpretation": "insufficient_midi_evidence"})
                continue
            a, b = base, motifs[dest]
            overlap = round(len(a & b) / min(len(a), len(b)), 4)
            comparisons.append({"reference": anchor, "target": dest, "pattern_overlap": overlap,
                                "interpretation": "interval_ngram_heuristic_only"})
            if overlap < 0.2:
                flags.append("low_interval_pattern_overlap_review")
    human = _review(Path(review) if review else None, seen)
    if not human["complete"]:
        flags.append("human_listening_review_incomplete")
    if fixture:
        flags.append("synthetic_fixture")
    # Every automatic recommendation is a review prompt, not an artistic verdict.
    queue = [{"destination": e["destination"], "track_sha256": e["track_sha256"],
              "role": e["role"], "scene": e["planned_scene"],
              "prompts": ["Does the music fit the intended scene?",
                          "Is a shared motif recognizable where appropriate?",
                          "Does the loop sound natural on real playback?",
                          "Are gameplay cues and effects audible against the mix?"]}
             for e in results]
    report = {"schema": REPORT_SCHEMA, "evidence_class": "synthetic_sound_director_fixture" if fixture
              else "local_source_audio_heuristics",
              "technical_status": "REVIEW" if flags else "PASS",
              "promotion_gate": "HOLD", "track_count": len(results),
              "tracks": results, "motif_comparisons": comparisons,
              "reference_destination": anchor, "human_review": human,
              "flags": sorted(set(flags)),
              "source_sha256": {"brief": _sha(brief)},
              "limits": ["MIDI interval overlap is NOT proof of shared musical identity or copyright.",
                         "Densest MIDI track/channel is only a melody proxy; chords can mislead.",
                         "Loop seam sample jump does not prove an audible click or a clean loop.",
                         "Role and planned scene are user intentions, NOT measured game use.",
                         "Listening scores are supplied claims, not verified objective measurements.",
                         "No audio output, player enjoyment, actual mix or synced capture validated."]}
    output.mkdir(parents=True, exist_ok=True)
    for name in ("evaluation.json", "review-queue.json", "review-template.json"):
        if (output / name).is_symlink():
            raise SoundDirectorError("symlinked evidence output forbidden")
    _write(output / "evaluation.json", report)
    _write(output / "review-queue.json", {"schema": REPORT_SCHEMA, "items": queue})
    _write(output / "review-template.json", {"schema": REVIEW_SCHEMA, "reviewer": "",
           "assessments": [{"destination": e["destination"],
                            **{metric: None for metric in SCORES}, "notes": ""}
                           for e in results]})
    return report
