"""Bounded, offline Godot engine-state probe for MGSF Sound Identity Lab M0.3.

Important: headless Godot uses the Dummy audio driver. A successful probe proves
engine calls/state transitions, NOT an audible waveform, in-game scene wiring,
or a player's musical experience. Production promotion always remains HOLD.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

SCHEMA = "mgsf.sound_identity.engine_state.v0.3"
MAP_SCHEMA = "mgsf.sound_identity.godot_map.v0.2"
ALLOWED_ROOT = "audio/mgsf_sound_identity/"
MAX_TRACKS = 12
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DEST_RE = re.compile(r"^res://audio/mgsf_sound_identity/[a-z0-9_]+_[0-9a-f]{16}\.wav$")


class SoundRuntimeError(ValueError):
    """Invalid runtime probe input or evidence."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def load_verified_audio_map(project: str | Path) -> list[dict]:
    """Validate every reference before the engine can read an asset."""
    project = Path(project)
    if not project.is_dir() or not (project / "project.godot").is_file():
        raise SoundRuntimeError("a Godot project with project.godot is required")
    if project.is_symlink():
        raise SoundRuntimeError("symlinked project root is not allowed")
    map_path = project / "audio/mgsf_sound_identity/sound_map.json"
    if map_path.is_symlink() or not map_path.is_file():
        raise SoundRuntimeError("M0.2 sound_map.json not found or unsafe")
    if map_path.stat().st_size > 512 * 1024:
        raise SoundRuntimeError("sound map exceeds size limit")
    try:
        spec = json.loads(map_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SoundRuntimeError("invalid Godot audio map JSON") from exc
    if not isinstance(spec, dict) or spec.get("schema") != MAP_SCHEMA:
        raise SoundRuntimeError("wrong audio map schema")
    tracks = spec.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= MAX_TRACKS:
        raise SoundRuntimeError("track count must be in 1..12")
    result, seen = [], set()
    base = project.resolve()
    for item in tracks:
        if not isinstance(item, dict):
            raise SoundRuntimeError("track entry must be an object")
        dest = item.get("destination")
        sha = item.get("sha256")
        loop = item.get("loop_requested")
        if not isinstance(dest, str) or not DEST_RE.fullmatch(dest):
            raise SoundRuntimeError("track destination violates dedicated Godot path")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise SoundRuntimeError("invalid track checksum")
        if type(loop) is not bool:
            raise SoundRuntimeError("loop_requested must be boolean")
        if dest in seen:
            raise SoundRuntimeError("duplicate audio destination")
        seen.add(dest)
        relative = Path(dest[len("res://"):])
        asset = project / relative
        current = project
        for component in relative.parts:
            current = current / component
            if current.is_symlink():
                raise SoundRuntimeError("symlinked audio asset/path is not allowed")
        if not asset.is_file() or not asset.resolve().is_relative_to(base):
            raise SoundRuntimeError("missing or escaping Godot audio asset")
        if not 0 < asset.stat().st_size <= 30 * 1024 * 1024:
            raise SoundRuntimeError("invalid WAV size")
        if _sha(asset) != sha:
            raise SoundRuntimeError("WAV checksum does not match M0.2 manifest")
        result.append({"path": str(asset.resolve()), "sha256": sha, "loop_requested": loop,
                       "destination": dest})
    return result


def verify_engine_evidence(probe: object, expected: list[dict]) -> list[str]:
    """Cross-check engine output against preflight, never trust self-reported success."""
    errors = []
    if not isinstance(probe, dict) or probe.get("schema") != SCHEMA:
        return ["invalid_engine_evidence_schema"]
    if not isinstance(probe.get("driver"), str) or not probe["driver"]:
        errors.append("missing_audio_driver")
    if not isinstance(probe.get("engine_version"), str) or not probe["engine_version"]:
        errors.append("missing_engine_version")
    observations = probe.get("observations")
    if not isinstance(observations, list) or len(observations) != len(expected):
        return errors + ["missing_or_extra_observations"]
    previous = ""
    last_time = -1
    for index, (obs, track) in enumerate(zip(observations, expected)):
        if not isinstance(obs, dict):
            errors.append(f"invalid_observation_{index}")
            continue
        if obs.get("sha256") != track["sha256"] or obs.get("switched_after") != previous:
            errors.append(f"wrong_source_or_transition_{index}")
        if any(obs.get(key) is not True for key in ("load_ok", "started", "stopped", "loop_configured")):
            errors.append(f"play_state_not_confirmed_{index}")
        at = obs.get("timestamp_ms")
        if type(at) is not int or at < last_time or at < 0:
            errors.append(f"nonmonotonic_engine_timestamp_{index}")
        else:
            last_time = at
        previous = track["sha256"]
    if probe.get("engine_checks_passed") is not True:
        errors.append("engine_did_not_report_success")
    return errors


def run_sound_runtime(project: str | Path, godot: str, output_root: str | Path,
                      *, fixture: bool = False, timeout: int = 60) -> dict:
    """Run the actual Godot process, preserve stdout+JSON hashes, never promote."""
    project = Path(project).absolute()
    output = Path(output_root).absolute()
    if output.resolve().is_relative_to(project.resolve()):
        raise SoundRuntimeError("evidence output must be outside Godot project")
    if timeout < 1 or timeout > 300:
        raise SoundRuntimeError("timeout must be 1..300 seconds")
    tracks = load_verified_audio_map(project)
    executable = shutil.which(str(godot))
    if executable is None and Path(godot).is_file():
        executable = str(Path(godot).resolve())
    if not executable:
        raise SoundRuntimeError("Godot executable not found")
    script = Path(__file__).with_name("sound_probe.gd")
    if not script.is_file():
        raise SoundRuntimeError("bundled GDScript audio probe missing")
    output.mkdir(parents=True, exist_ok=True)
    spec_path = output / "input-spec.json"
    engine_path = output / "engine-state.json"
    log_path = output / "godot-run.json"
    eval_path = output / "evaluation.json"
    for path in (spec_path, engine_path, log_path, eval_path):
        if path.is_symlink():
            raise SoundRuntimeError("evidence output symlink not allowed")
    engine_path.unlink(missing_ok=True)
    spec = {"schema": "mgsf.sound_identity.engine_input.v0.3", "tracks": tracks,
            "result_path": str(engine_path)}
    _write(spec_path, spec)
    command = [executable, "--headless", "--path", str(project), "--script", str(script.resolve())]
    env = os.environ.copy()
    env["MGSF_SOUND_PROBE_SPEC"] = str(spec_path)
    begun = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=project, env=env, capture_output=True,
                                   text=True, errors="replace", timeout=timeout)
        returncode = completed.returncode
        stdout, stderr = completed.stdout[-50000:], completed.stderr[-50000:]
    except subprocess.TimeoutExpired as exc:
        returncode = None
        stdout = str(exc.stdout or "")[-50000:]
        stderr = str(exc.stderr or "")[-50000:]
    elapsed_ms = int((time.monotonic() - begun) * 1000)
    runner = {"schema": "mgsf.sound_identity.runner.v0.3",
              "command": command, "returncode": returncode, "elapsed_ms": elapsed_ms,
              "stdout_tail": stdout, "stderr_tail": stderr, "spec_sha256": _sha(spec_path)}
    _write(log_path, runner)
    probe = None
    if engine_path.is_file() and engine_path.stat().st_size <= 1024 * 1024:
        try:
            probe = json.loads(engine_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    errors = verify_engine_evidence(probe, tracks)
    if returncode != 0:
        errors.append("engine_process_failed_or_timed_out")
    if "MGSF_SOUND_ENGINE_STATE_OK" not in stdout:
        errors.append("engine_success_marker_missing")
    if "ERROR:" in stdout or "SCRIPT ERROR:" in stdout or "SCRIPT ERROR:" in stderr:
        errors.append("engine_error_log")
    status = "PASS" if not errors else "FAIL"
    report = {
        "schema": "mgsf.sound_identity.runtime_eval.v0.3",
        "technical_status": status, "promotion_gate": "HOLD",
        "evidence_class": "synthetic_wav_real_engine_probe" if fixture else "user_supplied_wav_engine_probe",
        "observed_audio": False,
        "engine_driver": probe.get("driver") if isinstance(probe, dict) else None,
        "engine_state_verified": status == "PASS",
        "track_count": len(tracks), "errors": errors,
        "files": {"input_spec_sha256": _sha(spec_path), "runner_sha256": _sha(log_path),
                  "engine_state_sha256": _sha(engine_path) if engine_path.is_file() else None},
        "limitations": ["Headless Dummy driver proves no audible waveform",
                        "Not proof of game scene wiring, loop seam, mix balance, or human listening",
                        "Godot may create .godot/ cache in project; no game assets or scenes rewritten",
                        "Promotion requires human listening and actual gameplay capture"],
    }
    _write(eval_path, report)
    return report
