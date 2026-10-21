"""Offline, license-conscious intake planning for human-selected MusMus BGM.

This module NEVER downloads, decodes, modifies, uploads, or copies audio.
It handles human-authored catalog metadata and checks local file presence only.
All generated evidence stays HOLD pending human listening and license review.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

SITE = "https://musmus.main.jp/"
TERMS = "https://musmus.main.jp/info.html"
SCHEMA_VERSION = 1
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MODES = {"unknown", "none", "full", "intro"}


class MusMusIntakeError(ValueError):
    """Malformed or unsafe intake metadata."""


def _label(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise MusMusIntakeError(f"{field} must be a nonempty string (max 160 chars)")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise MusMusIntakeError(f"{field} cannot contain control characters")
    return value.strip()


def _source_url(value: object) -> str:
    url = _label(value, "source_page")
    try:
        parts = urlsplit(url)
        safe_host = parts.hostname == "musmus.main.jp" and parts.port in (None, 443)
    except ValueError as exc:
        raise MusMusIntakeError("source_page is not a valid URL") from exc
    if (
        parts.scheme != "https"
        or not safe_host
        or parts.username is not None
        or parts.password is not None
        or parts.path.lower().endswith((".ogg", ".mp3", ".wav", ".zip"))
    ):
        raise MusMusIntakeError("source_page must be a MusMus HTTPS web page, not a media URL")
    return url


def _audio_path(root: Path, value: object) -> tuple[str, bool]:
    if value is None or value == "":
        return "", False
    if not isinstance(value, str) or "\\" in value:
        raise MusMusIntakeError("audio_path must be a relative POSIX path")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or ":" in relative.parts[0]
        or ".." in relative.parts
        or "." in relative.parts
        or relative.suffix.lower() not in {".ogg", ".mp3"}
    ):
        raise MusMusIntakeError("audio_path must stay in the project and end in .ogg or .mp3")
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise MusMusIntakeError("audio_path cannot traverse symbolic links")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise MusMusIntakeError("audio_path escapes project root")
    return str(relative), candidate.is_file()


def _track(value: object, root: Path) -> dict:
    if not isinstance(value, dict):
        raise MusMusIntakeError("each track must be an object")
    track_id = _label(value.get("id"), "id")
    if not _ID_RE.fullmatch(track_id):
        raise MusMusIntakeError("id must be lowercase letters, numbers, _ or -")
    title = _label(value.get("title"), "title")
    url = _source_url(value.get("source_page", SITE))
    selected = value.get("selected_by_human", False)
    reviewed = value.get("license_reviewed", False)
    if type(selected) is not bool or type(reviewed) is not bool:
        raise MusMusIntakeError("selection and license review flags must be booleans")
    mode = value.get("loop_mode", "unknown")
    if not isinstance(mode, str) or mode not in _MODES:
        raise MusMusIntakeError(f"invalid loop_mode for {track_id}")
    offset = value.get("loop_offset_seconds")
    if offset is not None:
        if type(offset) not in (int, float) or not math.isfinite(offset) or offset < 0:
            raise MusMusIntakeError("loop_offset_seconds must be a finite nonnegative number")
        if mode != "intro" or offset == 0:
            raise MusMusIntakeError("positive loop_offset_seconds requires loop_mode=intro")
    path, present = _audio_path(root, value.get("audio_path"))
    if mode in {"intro", "full"} and path.lower().endswith(".mp3"):
        raise MusMusIntakeError("looping intake must use an OGG path")
    checks = []
    if not selected:
        checks.append("HUMAN_SELECTION_PENDING")
    if not reviewed:
        checks.append("LICENSE_REVIEW_PENDING")
    if not path or not present:
        checks.append("OFFICIAL_AUDIO_NOT_PRESENT")
    if mode == "unknown":
        checks.append("LOOP_MODE_UNCONFIRMED")
    if mode == "intro" and offset is None:
        checks.append("LOOP_OFFSET_UNCONFIRMED")
    return {
        "id": track_id,
        "title": title,
        "source_page": url,
        "audio_path": path,
        "audio_present": present,
        "selected_by_human": selected,
        "license_reviewed": reviewed,
        "loop_mode": mode,
        "loop_offset_seconds": offset,
        "checks": checks,
        "intake_state": "READY_FOR_MANUAL_PLAYBACK" if not checks else "NEEDS_REVIEW",
    }


def _engine_notes(tracks: list[dict]) -> str:
    rows = [
        "# MusMus BGM integration notes",
        "",
        "Manual instructions only. Nothing here proves playback or a license grant.",
        f"Source: {SITE}",
        f"Review current terms before release: {TERMS}",
        "",
        "## Godot 4.7",
        "",
        "1. Download selected OGG tracks yourself from MusMus, following its website rules.",
        "2. Import your own file into the target game project (this tool never copies media).",
        "3. For full loops enable the OGG importer's `loop` property.",
        "4. For intro loops configure `loop_offset` in seconds after verifying the",
        "   actual loop start by listening. LOOPSTART/LOOPLENGTH OGG tags are not",
        "   assumed to be consumed by Godot automatically; they can use sample units.",
        "5. Replay across multiple boundaries and listen for gaps or unexpected restarts.",
        "",
        "## Unity",
        "",
        "1. Import your own file into the Unity project's Assets directory.",
        "2. AudioSource.loop is only a full-clip repeat; do not assume intro loop tags work.",
        "3. An intro loop needs a separately tested runtime strategy; do not infer one.",
        "4. Run manual tests of loop points, transitions and relative music volume.",
        "",
        "## License / release gate",
        "",
        "- Use as background music in a game, keep the required MusMus credit.",
        "- Do not reshare tracks as a standalone music pack or vendor them in this repo.",
        "- No AI training, audio analysis for AI arrangement, remixing or stem extraction.",
        "- No automatic downloading, audio decoding, editing or media uploads.",
        "- Re-check official terms, final game packaging and credits before distribution.",
        "- All generated metadata is advisory and the release gate remains HOLD.",
        "",
        "## Candidate checklist",
        "",
    ]
    for track in tracks:
        hint = (
            f"{track['loop_offset_seconds']} s (human-provided; verify)"
            if track["loop_offset_seconds"] is not None
            else "not verified"
        )
        rows.append(
            f"- {track['id']}: {track['title']} | {track['loop_mode']} | "
            f"loop offset: {hint} | {track['intake_state']}"
        )
    return "\n".join(rows) + "\n"


def run_musmus_intake(manifest: Path, project_root: Path, output_root: Path) -> Path:
    """Validate human-authored metadata and write a non-promotable intake bundle."""
    root = project_root.resolve()
    if not root.is_dir():
        raise MusMusIntakeError("project_root must be an existing directory")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MusMusIntakeError(f"cannot read manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise MusMusIntakeError("manifest schema_version must be 1")
    project = _label(payload.get("project"), "project")
    raw_tracks = payload.get("tracks")
    if not isinstance(raw_tracks, list) or not raw_tracks or len(raw_tracks) > 100:
        raise MusMusIntakeError("tracks must contain between 1 and 100 entries")
    tracks = [_track(value, root) for value in raw_tracks]
    if len({track["id"] for track in tracks}) != len(tracks):
        raise MusMusIntakeError("duplicate track IDs")
    if output_root.is_symlink():
        raise MusMusIntakeError("output_root cannot be a symbolic link")
    out = output_root.resolve()
    if out.is_symlink():
        raise MusMusIntakeError("output_root cannot be a symbolic link")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": SCHEMA_VERSION,
        "service": "musmus-bgm-intake",
        "project": project,
        "source": SITE,
        "terms": TERMS,
        "evidence_class": "human_authored_metadata_and_local_file_presence",
        "release_gate": "HOLD",
        "human_audio_review_required": True,
        "audio_decoded_or_modified": False,
        "audio_copied_or_downloaded": False,
        "tracks": tracks,
    }
    selected = [t for t in tracks if t["selected_by_human"]]
    credits = [
        "Draft music credits (verify tracks actually used before release)",
        "",
        "BGM: MusMus",
        "https://musmus.main.jp/",
        "",
    ]
    credits.extend(f"- {t['title']} ({t['source_page']})" for t in selected)
    if not selected:
        credits.append("(No tracks have been confirmed by a human yet.)")
    (out / "intake-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "CREDITS-draft.txt").write_text("\n".join(credits) + "\n", encoding="utf-8")
    (out / "ENGINE-NOTES.md").write_text(_engine_notes(tracks), encoding="utf-8")
    return out
