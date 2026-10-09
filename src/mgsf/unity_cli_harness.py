"""Provenance-safe Unity CLI/Pipeline probe and optional EditMode test harness.

MGSF-UNITY-M0.7 intentionally avoids arbitrary Unity C# eval and editor mutations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import os
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class UnityHarnessResult:
    root: Path
    status: str
    reason: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _envelope(stdout: str) -> dict[str, Any] | None:
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("success") is not True or data.get("error") or "data" not in data:
        return None
    return data


def _ready_projects(value: Any) -> list[str]:
    """Accept only explicit ready Editor/project pairs, never text matches."""
    found: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            state = str(item.get("state", item.get("status", ""))).lower()
            project = item.get("project_path", item.get("projectPath", item.get("project")))
            if isinstance(project, dict):
                project = project.get("path", project.get("projectPath"))
            if state == "ready" and isinstance(project, str) and project.strip():
                found.append(project)
            for child in item.values():
                if isinstance(child, (dict, list)):
                    visit(child)

    visit(value)
    return found


def _project_key(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def _valid_project(project: Path) -> bool:
    return (project / "ProjectSettings" / "ProjectVersion.txt").is_file() and (project / "Assets").is_dir()


def _record_step(
    name: str,
    command: list[str],
    root: Path,
    *,
    project: Path,
    executable: str,
    timeout: int,
    fixture_data: dict[str, Any] | None,
) -> dict[str, Any]:
    start = _now()
    if fixture_data is not None:
        step = fixture_data.get("steps", {}).get(name, {})
        returncode = step.get("returncode", 1)
        stdout = step.get("stdout", "")
        stderr = step.get("stderr", "")
        if not isinstance(returncode, int) or not isinstance(stdout, str) or not isinstance(stderr, str):
            raise ValueError("fixture step must have integer returncode and string stdout/stderr")
        origin = "deterministic_fixture"
    else:
        origin = "local_unity_cli"
        try:
            env = os.environ.copy()
            env["UNITY_PROJECT_PATH"] = str(project)
            completed = subprocess.run(
                [executable, *command],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
                timeout=timeout,
            )
            returncode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except subprocess.TimeoutExpired:
            returncode, stdout, stderr = 124, "", "Unity CLI invocation timed out"
        except OSError as exc:
            returncode, stdout, stderr = 127, "", f"Unity CLI unavailable: {type(exc).__name__}"
    stdout_path = root / f"{name}.stdout.txt"
    stderr_path = root / f"{name}.stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    data = _envelope(stdout)
    return {
        "name": name,
        "origin": origin,
        "command": [executable, *command],
        "started_at": start,
        "finished_at": _now(),
        "returncode": returncode,
        "stdout_path": stdout_path.name,
        "stdout_sha256": _sha(stdout.encode("utf-8")),
        "stderr_path": stderr_path.name,
        "stderr_sha256": _sha(stderr.encode("utf-8")),
        "envelope_success": data is not None,
        "data": data,
    }


def _nunit_verdict(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        root = ET.parse(path).getroot()
        if root.tag not in {"test-run", "test-results"}:
            return None
        total = int(root.attrib["total"])
        failures = int(root.attrib.get("failed", root.attrib.get("failures", "0")))
        skipped = int(root.attrib.get("skipped", root.attrib.get("ignored", "0")))
        inconclusive = int(root.attrib.get("inconclusive", "0"))
        passed = int(root.attrib.get("passed", str(total - failures - skipped - inconclusive)))
        if total < 1 or failures < 0 or skipped < 0 or inconclusive < 0 or passed < 1:
            return None
        return {
            "total": total,
            "passed": passed,
            "failed": failures,
            "skipped": skipped,
            "inconclusive": inconclusive,
            "sha256": _sha(path.read_bytes()),
            "bytes": path.stat().st_size,
        }
    except (ET.ParseError, KeyError, ValueError, OSError):
        return None


def run_unity_harness(
    project: str | Path,
    output_root: str | Path,
    *,
    unity: str = "unity",
    run_tests: bool = False,
    timeout_seconds: int = 120,
    fixture: str | Path | None = None,
) -> UnityHarnessResult:
    project_path = Path(project).resolve()
    if not _valid_project(project_path):
        raise ValueError(f"not a Unity project (Assets/ and ProjectSettings/ProjectVersion.txt required): {project_path}")
    if not 1 <= timeout_seconds <= 7200:
        raise ValueError("timeout_seconds must be between 1 and 7200")
    if not unity.strip():
        raise ValueError("unity executable must not be empty")

    fixture_data: dict[str, Any] | None = None
    if fixture is not None:
        fixture_data = json.loads(Path(fixture).read_text(encoding="utf-8"))
        if not isinstance(fixture_data, dict) or fixture_data.get("schema_version") != 1:
            raise ValueError("Unity fixture schema_version must be 1")

    # Each run owns a fresh directory. Old reports must never satisfy a new run.
    suffix = uuid.uuid4().hex[:12]
    root = Path(output_root).resolve() / f"{project_path.name}-{suffix}"
    root.mkdir(parents=True, exist_ok=False)
    record: dict[str, Any] = {
        "schema_version": 1,
        "service": "unity-cli-pipeline-agent-harness",
        "milestone": "MGSF-UNITY-M0.7",
        "project": str(project_path),
        "evidence_class": "deterministic_unity_fixture" if fixture_data is not None else "recorded_unity_cli",
        "started_at": _now(),
        "run_tests_requested": run_tests,
        "steps": [],
        "test_report": None,
        "status": "HOLD",
        "reason": "not evaluated",
    }

    def step(name: str, command: list[str]) -> dict[str, Any]:
        value = _record_step(
            name, command, root, project=project_path, executable=unity,
            timeout=timeout_seconds, fixture_data=fixture_data,
        )
        record["steps"].append({key: item for key, item in value.items() if key != "data"})
        return value

    try:
        if fixture_data is not None:
            # Deliberately no subprocess call in fixture mode, regardless of flags.
            for name, command in (
                ("version", ["version", "--format", "json"]),
                ("status", ["status", "--format", "json"]),
                ("manifest", ["list", "--project-path", str(project_path), "--format", "json"]),
            ):
                step(name, command)
            record["reason"] = "fixture evidence is never proof of a connected Unity Editor"
        else:
            version = step("version", ["version", "--format", "json"])
            if version["returncode"] != 0 or not version["envelope_success"]:
                record["reason"] = "Unity CLI version probe failed"
            else:
                status = step("status", ["status", "--format", "json"])
                ready = _ready_projects(status["data"])
                if status["returncode"] != 0 or not status["envelope_success"]:
                    record["reason"] = "Unity Pipeline/Editor status unavailable"
                elif len(ready) != 1 or _project_key(ready[0]) != _project_key(project_path):
                    record["reason"] = "cannot verify one ready Unity Editor bound to the requested project"
                else:
                    manifest = step("manifest", ["list", "--project-path", str(project_path), "--format", "json"])
                    if (manifest["returncode"] != 0 or not manifest["envelope_success"]
                            or not manifest["data"].get("data")):
                        record["reason"] = "Unity Pipeline command manifest unavailable or empty"
                    elif not run_tests:
                        record["reason"] = "read-only connection verified; EditMode tests not requested"
                    else:
                        report = root / "editmode-results.xml"
                        command = [
                            "test", str(project_path), "--mode", "EditMode",
                            "--output", str(report), "--format", "json",
                        ]
                        tested = step("editmode_tests", command)
                        verdict = _nunit_verdict(report)
                        if verdict:
                            record["test_report"] = {"path": report.name, **verdict}
                        if tested["returncode"] == 8 or (verdict and verdict["failed"] > 0):
                            record["status"] = "ITERATE"
                            record["reason"] = "Unity EditMode tests reported failures"
                        elif tested["returncode"] != 0 or not tested["envelope_success"] or not verdict:
                            record["reason"] = "Unity EditMode run lacks a successful CLI result and nonempty NUnit report"
                        elif verdict["failed"] == 0:
                            record["status"] = "PASS"
                            record["reason"] = "real Unity CLI/Pipeline and EditMode NUnit evidence verified"
    finally:
        record["finished_at"] = _now()
        _write_json(root / "evaluation.json", record)

    return UnityHarnessResult(root=root, status=record["status"], reason=record["reason"])
