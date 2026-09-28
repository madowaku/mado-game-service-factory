from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .gameplay_capture import CapturePlaytestRun, run_capture_playtest

ADAPTER_ID = "godot-capture-adapter"
ADAPTER_VERSION = "0.3b.1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class GodotCaptureAdapterError(RuntimeError):
    """Raised when a Godot capture run cannot produce trustworthy evidence."""


@dataclass(frozen=True)
class GodotCaptureAdapterRun:
    root: Path
    raw_capture_root: Path
    runtime_log_path: Path
    adapter_eval_path: Path
    status: str
    capture_playtest: CapturePlaytestRun


def _git_head(project_dir: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _validate_executable(path: str | Path) -> str:
    value = str(path)
    resolved = shutil.which(value)
    if resolved is not None:
        return resolved
    candidate = Path(value)
    if candidate.is_file():
        return str(candidate.resolve())
    raise GodotCaptureAdapterError(f"Godot executable not found: {value}")


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    log_path: Path,
    label: str,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        log_path.write_text(
            f"label={label}\n"
            f"command={' '.join(command)}\n"
            "returncode=TIMEOUT\n"
            "--- stdout ---\n"
            f"{stdout}\n"
            "--- stderr ---\n"
            f"{stderr}\n",
            encoding="utf-8",
            newline="\n",
        )
        tail = "\n".join((stdout + "\n" + stderr).splitlines()[-30:])
        raise GodotCaptureAdapterError(
            f"{label} timed out; see {log_path}\nGodot output tail:\n{tail}"
        ) from exc
    except OSError as exc:
        log_path.write_text(
            f"label={label}\n"
            f"command={' '.join(command)}\n"
            f"launch_error={exc}\n",
            encoding="utf-8",
            newline="\n",
        )
        raise GodotCaptureAdapterError(
            f"{label} failed to start; see {log_path}"
        ) from exc

    log_path.write_text(
        f"label={label}\n"
        f"command={' '.join(command)}\n"
        f"returncode={completed.returncode}\n"
        "--- stdout ---\n"
        f"{completed.stdout}\n"
        "--- stderr ---\n"
        f"{completed.stderr}\n",
        encoding="utf-8",
        newline="\n",
    )
    return completed


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None
    if len(header) < 24 or header[:8] != PNG_SIGNATURE:
        return None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width, height


def run_godot_capture_adapter(
    project_dir: str | Path,
    godot_executable: str | Path,
    output_root: str | Path = "evidence",
    scene: str = "res://scenes/capture/mgsf_c6_capture.tscn",
    command_prefix: Sequence[str] = (),
    source_head_sha: str | None = None,
) -> GodotCaptureAdapterRun:
    project = Path(project_dir).resolve()
    if not (project / "project.godot").is_file():
        raise GodotCaptureAdapterError(
            f"project.godot was not found under: {project}"
        )

    godot = _validate_executable(godot_executable)
    root = Path(output_root).resolve() / ADAPTER_ID / "vertical-slice-c6-direct"
    raw_capture_root = root / "raw-capture"
    raw_capture_root.mkdir(parents=True, exist_ok=True)

    preflight_log_path = root / "godot-preflight.log"
    runtime_log_path = root / "godot-runtime.log"
    adapter_eval_path = root / "adapter_eval.json"

    source_sha = source_head_sha or _git_head(project)
    env = os.environ.copy()
    env["MGSF_CAPTURE_DIR"] = str(raw_capture_root)
    env["MGSF_SOURCE_HEAD_SHA"] = source_sha

    # A fresh checkout may not yet have Godot's generated global class cache.
    # Run the same editor import/parse preflight used by the source project CI.
    preflight_command = [
        godot,
        "--headless",
        "--editor",
        "--path",
        str(project),
        "--quit-after",
        "1",
    ]
    preflight = _run_command(
        preflight_command,
        cwd=project,
        env=env,
        timeout=45,
        log_path=preflight_log_path,
        label="Godot preflight",
    )
    if preflight.returncode != 0:
        raise GodotCaptureAdapterError(
            f"Godot preflight failed; see {preflight_log_path}"
        )

    command = [
        *command_prefix,
        godot,
        "--path",
        str(project),
        "--scene",
        scene,
    ]
    completed = _run_command(
        command,
        cwd=project,
        env=env,
        timeout=45,
        log_path=runtime_log_path,
        label="Godot direct capture",
    )

    capture_json = raw_capture_root / "capture.json"
    timeline_jsonl = raw_capture_root / "timeline.jsonl"
    before_png = raw_capture_root / "before-swing.png"
    reveal_png = raw_capture_root / "reveal.png"

    process_ok = completed.returncode == 0 and "MGSF_CAPTURE_OK" in completed.stdout
    files_ok = all(
        path.is_file() and path.stat().st_size > 0
        for path in (capture_json, timeline_jsonl, before_png, reveal_png)
    )

    dimensions = {
        "before-swing.png": _png_dimensions(before_png),
        "reveal.png": _png_dimensions(reveal_png),
    }
    png_ok = all(
        value is not None and value[0] >= 100 and value[1] >= 100
        for value in dimensions.values()
    )

    if not process_ok or not files_ok or not png_ok:
        _write_json(
            adapter_eval_path,
            {
                "adapter": ADAPTER_ID,
                "version": ADAPTER_VERSION,
                "status": "FAIL",
                "criteria": {
                    "godot_preflight_passed": True,
                    "godot_process_passed": process_ok,
                    "capture_files_exist": files_ok,
                    "png_frames_valid": png_ok,
                },
                "dimensions": {
                    key: list(value) if value is not None else None
                    for key, value in dimensions.items()
                },
                "source_head_sha": source_sha,
                "preflight_log": str(preflight_log_path),
                "runtime_log": str(runtime_log_path),
            },
        )
        raise GodotCaptureAdapterError(
            f"Godot capture did not produce valid direct evidence; see {runtime_log_path}"
        )

    capture_payload = json.loads(capture_json.read_text(encoding="utf-8"))
    evidence_class = capture_payload.get("source", {}).get("evidence_class")
    direct_class_ok = evidence_class == "recorded_gameplay_capture"
    source_sha_ok = (
        capture_payload.get("source", {}).get("source_head_sha") == source_sha
    )

    capture_playtest = run_capture_playtest(raw_capture_root, Path(output_root))

    criteria = {
        "godot_preflight_passed": True,
        "godot_process_passed": process_ok,
        "capture_files_exist": files_ok,
        "png_frames_valid": png_ok,
        "recorded_gameplay_capture": direct_class_ok,
        "source_sha_preserved": source_sha_ok,
        "capture_eval_passed": capture_playtest.capture.eval_status == "PASS",
        "capture_playtest_passed": capture_playtest.status == "PASS",
        "direct_media_reaches_finding": False,
    }

    report = json.loads(
        (capture_playtest.report_root / "report.json").read_text(encoding="utf-8")
    )
    if report.get("findings"):
        criteria["direct_media_reaches_finding"] = all(
            finding.get("evidence", {})
            .get("capture_policy", {})
            .get("media_is_direct_gameplay")
            is True
            and bool(finding.get("evidence", {}).get("media_evidence"))
            for finding in report["findings"]
        )

    status = "PASS" if all(criteria.values()) else "FAIL"
    _write_json(
        adapter_eval_path,
        {
            "adapter": ADAPTER_ID,
            "version": ADAPTER_VERSION,
            "status": status,
            "criteria": criteria,
            "dimensions": {
                key: list(value) if value is not None else None
                for key, value in dimensions.items()
            },
            "source_head_sha": source_sha,
            "project": str(project),
            "scene": scene,
            "preflight_log": str(preflight_log_path),
            "runtime_log": str(runtime_log_path),
            "raw_capture_root": str(raw_capture_root),
            "capture_evidence_root": str(capture_playtest.capture.root),
            "report_root": str(capture_playtest.report_root),
            "finding_count": capture_playtest.finding_count,
        },
    )

    return GodotCaptureAdapterRun(
        root=root,
        raw_capture_root=raw_capture_root,
        runtime_log_path=runtime_log_path,
        adapter_eval_path=adapter_eval_path,
        status=status,
        capture_playtest=capture_playtest,
    )
