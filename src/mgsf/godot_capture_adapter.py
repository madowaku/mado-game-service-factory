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
ADAPTER_VERSION = "0.3b.0"


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

    runtime_log_path = root / "godot-runtime.log"
    adapter_eval_path = root / "adapter_eval.json"

    source_sha = source_head_sha or _git_head(project)
    env = os.environ.copy()
    env["MGSF_CAPTURE_DIR"] = str(raw_capture_root)
    env["MGSF_SOURCE_HEAD_SHA"] = source_sha

    command = [
        *command_prefix,
        godot,
        "--path",
        str(project),
        "--scene",
        scene,
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        runtime_log_path.write_text(
            f"command={' '.join(command)}\n"
            "returncode=TIMEOUT\n"
            "--- stdout ---\n"
            f"{stdout}\n"
            "--- stderr ---\n"
            f"{stderr}\n",
            encoding="utf-8",
            newline="\n",
        )
        raise GodotCaptureAdapterError(
            f"Godot capture timed out; see {runtime_log_path}"
        ) from exc
    except OSError as exc:
        runtime_log_path.write_text(
            f"command={' '.join(command)}\n"
            f"launch_error={exc}\n",
            encoding="utf-8",
            newline="\n",
        )
        raise GodotCaptureAdapterError(
            f"Godot capture process failed to start; see {runtime_log_path}"
        ) from exc

    runtime_text = (
        f"command={' '.join(command)}\n"
        f"returncode={completed.returncode}\n"
        "--- stdout ---\n"
        f"{completed.stdout}\n"
        "--- stderr ---\n"
        f"{completed.stderr}\n"
    )
    runtime_log_path.write_text(runtime_text, encoding="utf-8", newline="\n")

    capture_json = raw_capture_root / "capture.json"
    timeline_jsonl = raw_capture_root / "timeline.jsonl"
    before_png = raw_capture_root / "before-swing.png"
    reveal_png = raw_capture_root / "reveal.png"

    process_ok = (
        completed.returncode == 0
        and "MGSF_CAPTURE_OK" in completed.stdout
    )
    files_ok = all(
        path.is_file() and path.stat().st_size > 0
        for path in (capture_json, timeline_jsonl, before_png, reveal_png)
    )

    if not process_ok or not files_ok:
        _write_json(
            adapter_eval_path,
            {
                "adapter": ADAPTER_ID,
                "version": ADAPTER_VERSION,
                "status": "FAIL",
                "criteria": {
                    "godot_process_passed": process_ok,
                    "capture_files_exist": files_ok,
                },
                "source_head_sha": source_sha,
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
        "godot_process_passed": process_ok,
        "capture_files_exist": files_ok,
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
            "source_head_sha": source_sha,
            "project": str(project),
            "scene": scene,
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
