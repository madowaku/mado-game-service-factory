"""MGSF M0.9.1: independent Godot gameplay-state verification.

The fixture engine run is not proof that Godogen/Codex autonomously generated a
game. This gate explicitly separates runtime PASS from autonomous HOLD.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
from uuid import uuid4
import json
import os
import re
import shutil
import subprocess
from typing import Any

from .godogen_adapter import _run_step, _verify_video, _sha

MAX_TRACE_BYTES = 2 * 1024 * 1024
CHECK_KEYS = {"id", "start_tick", "end_tick", "axis", "input", "min_delta", "max_delta", "max_abs_delta"}


class StateVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class StateVerdict:
    root: Path
    status: str
    autonomous_status: str
    passed_checks: int
    total_checks: int


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _within(root: Path, rel: str, suffix: str) -> Path:
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
        raise StateVerificationError("artifact path must be project-relative")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix.lower() != suffix:
        raise StateVerificationError("artifact must stay inside the project and have the expected suffix")
    if not path.is_file() or path.stat().st_size <= 0:
        raise StateVerificationError("required artifact is absent or empty")
    return path


def load_contract(mission: str | Path) -> dict[str, Any]:
    data = json.loads(Path(mission).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise StateVerificationError("mission schema_version must be 1")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", str(data.get("mission_id", ""))):
        raise StateVerificationError("invalid mission_id")
    checks = data.get("state_checks")
    if not isinstance(checks, list) or len(checks) < 2 or len(checks) > 16:
        raise StateVerificationError("at least two state_checks are required")
    ids: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or not CHECK_KEYS.issuperset(check):
            raise StateVerificationError("invalid state_check")
        name = check.get("id")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", name) or name in ids:
            raise StateVerificationError("state_check ids must be unique and safe")
        ids.add(name)
        start, end = check.get("start_tick"), check.get("end_tick")
        if type(start) is not int or type(end) is not int or not (0 <= start < end <= 3600):
            raise StateVerificationError("invalid check tick window")
        if check.get("axis") not in ("x", "y"):
            raise StateVerificationError("axis must be x or y")
        if check.get("input") not in ("right", "left", "up", "down", "idle"):
            raise StateVerificationError("unsupported input action")
        bounds = [key for key in ("min_delta", "max_delta", "max_abs_delta") if key in check]
        if len(bounds) != 1:
            raise StateVerificationError("check requires exactly one delta bound")
        key = bounds[0]
        value = check[key]
        if type(value) not in (float, int) or not isfinite(value):
            raise StateVerificationError("delta bound must be finite")
        if (key == "min_delta" and value <= 0) or (key == "max_delta" and value >= 0):
            raise StateVerificationError("delta must have the required sign")
        if (key == "max_abs_delta" and value < 0) or ((key == "max_abs_delta") != (check["input"] == "idle")):
            raise StateVerificationError("idle requires a nonnegative max_abs_delta bound")
    return data


def verify_state(
    project: str | Path, mission_path: str | Path, *, trace_path: str,
    video_path: str, runner_record: dict[str, Any] | None,
    output_root: str | Path, fixture: bool = False, ffprobe: str = "ffprobe",
) -> StateVerdict:
    project = Path(project).resolve()
    mission = load_contract(mission_path)
    trace = _within(project, trace_path, ".json")
    video = _within(project, video_path, ".mp4")
    if trace.stat().st_size > MAX_TRACE_BYTES:
        raise StateVerificationError("trace exceeds size limit")
    data = json.loads(trace.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StateVerificationError("trace must be an object")
    if (data.get("schema_version"), data.get("mission_id"), data.get("engine")) != (
        1, mission["mission_id"], "godot",
    ):
        raise StateVerificationError("wrong state trace schema, mission or engine")
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{7,79}", run_id):
        raise StateVerificationError("invalid run_id")
    samples = data.get("samples")
    if not isinstance(samples, list) or not 10 <= len(samples) <= 3601:
        raise StateVerificationError("state trace must have between 10 and 3601 samples")
    by_tick: dict[int, dict[str, Any]] = {}
    last = -1
    for sample in samples:
        if not isinstance(sample, dict):
            raise StateVerificationError("invalid sample")
        tick = sample.get("tick")
        if type(tick) is not int or not last < tick <= 3600:
            raise StateVerificationError("ticks must increase without duplicates")
        last = tick
        state = sample.get("state")
        if not isinstance(state, dict):
            raise StateVerificationError("missing state object")
        for name in ("x", "y"):
            value = state.get(name)
            if type(value) not in (int, float) or not isfinite(value):
                raise StateVerificationError("state coordinates must be finite")
        if sample.get("input") not in ("idle", "right", "left", "up", "down"):
            raise StateVerificationError("unknown input action in trace")
        by_tick[tick] = sample

    results: list[dict[str, Any]] = []
    for check in mission["state_checks"]:
        first = by_tick.get(check["start_tick"])
        last_sample = by_tick.get(check["end_tick"])
        span = [s for tick, s in by_tick.items()
                if check["start_tick"] <= tick <= check["end_tick"]]
        matched_input = bool(span) and all(
            s["input"] == check["input"] for s in span
        )
        delta = (
            float(last_sample["state"][check["axis"]]) - float(first["state"][check["axis"]])
            if first and last_sample else None
        )
        limit_ok = delta is not None and (
            delta >= check["min_delta"] if "min_delta" in check else
            delta <= check["max_delta"] if "max_delta" in check else
            abs(delta) <= check["max_abs_delta"]
        )
        results.append({
            "id": check["id"], "input": check["input"],
            "start_tick": check["start_tick"], "end_tick": check["end_tick"],
            "axis": check["axis"], "delta": delta,
            "input_correlated": matched_input, "pass": bool(matched_input and limit_ok),
        })

    runner = runner_record if isinstance(runner_record, dict) else {}
    checks = runner.get("engine_checks", {})
    runner_ok = (
        runner.get("runner") == "mgsf-godot-runtime"
        and runner.get("returncode") == 0
        and runner.get("run_id") == run_id
        and runner.get("trace_sha256") == _sha(trace)
        and runner.get("video_sha256") == _sha(video)
        and isinstance(checks, dict)
        and all(isinstance(checks.get(key), dict) and checks[key].get("returncode") == 0
                for key in ("dotnet_build", "godot_import", "godot_capture", "ffmpeg_encode"))
    )
    video_ok, video_meta = _verify_video(video, ffprobe)
    status = (
        "HOLD" if fixture or not runner_ok else
        "PASS" if video_ok and all(r["pass"] for r in results) else "ITERATE"
    )
    root = Path(output_root) / mission["mission_id"] / run_id
    root.mkdir(parents=True, exist_ok=True)
    # Artifacts are copied after validation, never linked to potentially mutable external data.
    copy_trace = root / "state-trace.json"
    copy_video = root / "proof.mp4"
    if trace != copy_trace.resolve():
        shutil.copyfile(trace, copy_trace)
    if video != copy_video.resolve():
        shutil.copyfile(video, copy_video)
    evidence = {
        "schema_version": 1, "service": "godogen-gameplay-state-verification",
        "mission_id": mission["mission_id"], "run_id": run_id,
        "evidence_class": "deterministic_state_fixture" if fixture else "recorded_godot_engine_dogfood",
        "status": status,
        "autonomous_status": "HOLD",
        "autonomous_reason": "Godot engine dogfood does not prove Codex/Godogen generated a game",
        "runner_verified": runner_ok, "video_verified": video_ok,
        "video_probe": video_meta, "checks": results,
        "state_trace": {"path": "state-trace.json", "sha256": _sha(copy_trace), "samples": len(samples)},
        "video": {"path": "proof.mp4", "sha256": _sha(copy_video), "bytes": copy_video.stat().st_size},
        "runner": runner,
        "provenance_note": "Scripted engine input, not a human playtest or an autonomous game build",
    }
    _write(root / "state-evaluation.json", evidence)
    return StateVerdict(root, status, "HOLD", sum(int(r["pass"]) for r in results), len(results))


def live_dogfood(
    project: str | Path, mission_path: str | Path, output_root: str | Path, *,
    godot: str, dotnet: str = "dotnet", ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    xvfb: bool = True,
) -> StateVerdict:
    """Run the bounded bundled sample game, never arbitrary user game entrypoints."""
    project = Path(project).resolve()
    expected_marker = project / ".mgsf-gyro-dogfood"
    if not expected_marker.is_file() or expected_marker.read_text(encoding="utf-8").strip() != "mgsf-gyro-state-dogfood-v1":
        raise StateVerificationError("live-dogfood requires the explicitly marked GYRO fixture")
    mission = load_contract(mission_path)
    run_id = "live-" + uuid4().hex
    frames_dir = project / "screenshots" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    # Prevent mixing frame sequences from older runs.
    if any(frames_dir.iterdir()):
        raise StateVerificationError("capture frames directory must be empty")
    trace = project / "screenshots" / "state-trace.json"
    video = project / "screenshots" / "proof.mp4"
    if trace.exists() or video.exists():
        raise StateVerificationError("refusing to reuse pre-existing trace or video")
    checks = {
        "dotnet_build": _run_step([dotnet, "build", "--nologo"], project, 240),
    }
    if checks["dotnet_build"]["returncode"] != 0:
        _write(Path(output_root) / "failure-evidence/dotnet-build.json", checks["dotnet_build"])
        raise StateVerificationError("Godot .NET dogfood build failed: " + str(checks["dotnet_build"].get("stderr_tail", "")))
    checks["godot_import"] = _run_step([godot, "--headless", "--path", str(project), "--import"], project, 120)
    if checks["godot_import"]["returncode"] != 0:
        _write(Path(output_root) / "failure-evidence/godot-import.json", checks["godot_import"])
        raise StateVerificationError("Godot resource import failed: " + str(checks["godot_import"].get("stderr_tail", "")))
    argv = [godot, "--path", str(project), "--write-movie",
            str(frames_dir / "frame.png"), "--fixed-fps", "30", "--quit-after", "450",
            "--", "--mgsf-trace", str(trace), "--mgsf-run-id", run_id,
            "--mgsf-mission-id", mission["mission_id"]]
    if xvfb:
        argv = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", *argv]
    checks["godot_capture"] = _run_step(argv, project, 240)
    if checks["godot_capture"]["returncode"] != 0 or not trace.is_file():
        debug = Path(output_root) / "failure-evidence"
        _write(debug / "godot-capture.json", checks["godot_capture"])
        raise StateVerificationError(
            "real Godot capture did not produce state trace: "
            + str(checks["godot_capture"].get("stderr_tail", checks["godot_capture"].get("error", "")))
        )
    frames = list(frames_dir.glob("frame*.png"))
    if len(frames) < 400:
        raise StateVerificationError("too few real Godot movie frames")
    checks["ffmpeg_encode"] = _run_step(
        [ffmpeg, "-y", "-loglevel", "error", "-framerate", "30", "-i",
         str(frames_dir / "frame%08d.png"), "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video)],
        project, 180,
    )
    if checks["ffmpeg_encode"]["returncode"] != 0 or not video.is_file():
        raise StateVerificationError("real gameplay video encoding failed")
    runner = {
        "runner": "mgsf-godot-runtime", "run_id": run_id, "returncode": 0,
        "engine_checks": checks, "trace_sha256": _sha(trace), "video_sha256": _sha(video),
        "frame_count": len(frames),
        "source": "hand-authored MGSF GYRO fixture (not generated by Codex)",
    }
    verdict = verify_state(
        project, mission_path, trace_path="screenshots/state-trace.json",
        video_path="screenshots/proof.mp4", runner_record=runner,
        output_root=output_root, ffprobe=ffprobe,
    )
    _write(verdict.root / "runner.json", runner)
    return verdict
