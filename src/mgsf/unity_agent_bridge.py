from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree

ADAPTER_ID = "unity-official-agent-bridge"
Run = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class UnityBridgeResult:
    root: Path
    status: str
    verdict: str
    evidence_path: Path


def _project(project: str | Path) -> tuple[Path, str]:
    root = Path(project).expanduser().resolve()
    version_file = root / "ProjectSettings" / "ProjectVersion.txt"
    if not (root / "Assets").is_dir() or not version_file.is_file():
        raise ValueError("Unity project requires Assets/ and ProjectSettings/ProjectVersion.txt")
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("m_EditorVersion:"):
            version = line.split(":", 1)[1].strip()
            major = version.split(".", 1)[0]
            if not major.isdecimal() or int(major) < 6000:
                raise ValueError("Unity 6 (6000.x) or newer is required")
            return root, version
    raise ValueError("ProjectVersion.txt is missing m_EditorVersion")


def _cli(unity: str) -> str:
    if not unity or not unity.strip() or "\0" in unity:
        raise ValueError("Unity CLI executable must be a non-empty path or command")
    return unity


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _invoke(argv: list[str], project: Path, timeout: int, runner: Run) -> dict[str, Any]:
    try:
        proc = runner(argv, cwd=project, text=True, capture_output=True, check=False, timeout=timeout)
        stdout, stderr, code = proc.stdout or "", proc.stderr or "", proc.returncode
        error = None
    except (OSError, subprocess.TimeoutExpired) as exc:
        stdout, stderr, code, error = "", "", None, type(exc).__name__
    try:
        payload = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        payload = None
    return {
        "argv": argv,
        "returncode": code,
        "error_type": error,
        "stdout_sha256": _digest(stdout.encode("utf-8")),
        "stderr_sha256": _digest(stderr.encode("utf-8")),
        "response": payload if isinstance(payload, dict) else None,
    }


def _write_record(output_root: str | Path, operation: str, payload: dict[str, Any]) -> UnityBridgeResult:
    root = Path(output_root) / ADAPTER_ID / operation / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    path = root / "evaluation.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return UnityBridgeResult(root=root, status=payload["status"], verdict=payload["verdict"], evidence_path=path)


def engine_adapters() -> list[dict[str, str]]:
    # This registry is additive: existing Godot commands and their evidence path do not change.
    return [
        {"engine": "godot", "adapter": "godot-capture", "entrypoint": "mgsf godot-capture", "stage": "active"},
        {"engine": "unity", "adapter": ADAPTER_ID, "entrypoint": "mgsf unity-probe / unity-test", "stage": "incubation"},
    ]


def probe_unity(
    project: str | Path,
    output_root: str | Path = "evidence",
    *,
    unity: str = "unity",
    timeout_seconds: int = 30,
    runner: Run = subprocess.run,
) -> UnityBridgeResult:
    root, version = _project(project)
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")
    command = [_cli(unity), "status", "--project-path", str(root), "--format", "json", "--non-interactive"]
    invocation = _invoke(command, root, timeout_seconds, runner)
    response = invocation.pop("response")
    instances = response.get("data", {}).get("instances", []) if isinstance(response, dict) and isinstance(response.get("data"), dict) else []
    ready = bool(
        invocation["returncode"] == 0
        and response
        and response.get("success") is True
        and isinstance(instances, list)
        and any(
            isinstance(item, dict)
            and item.get("state") == "ready"
            and isinstance(item.get("project"), str)
            and Path(item["project"]).expanduser().resolve() == root
            for item in instances
        )
    )
    return _write_record(output_root, "probe", {
        "schema_version": 1, "service": ADAPTER_ID, "engine": "unity",
        "project": str(root), "editor_version": version,
        "evidence_class": "recorded_unity_cli_preflight",
        "status": "HOLD", "verdict": "READY" if ready else "UNAVAILABLE",
        "reason": "A ready Editor is connectivity evidence, not gameplay proof",
        "runner": invocation, "plugin_installed": "unverified",
    })


def _nunit_verdict(path: Path) -> tuple[bool, dict[str, int]]:
    if not path.is_file():
        return False, {}
    try:
        root = ElementTree.parse(path).getroot()
        if root.tag != "test-run":
            return False, {}
        counts = {key: int(root.attrib[key]) for key in ("total", "passed", "failed", "skipped")}
        ok = counts["total"] > 0 and counts["failed"] == 0 and counts["passed"] > 0 and (
            counts["passed"] + counts["failed"] + counts["skipped"] == counts["total"]
        )
        return ok, counts
    except (ElementTree.ParseError, KeyError, ValueError):
        return False, {}


def run_unity_tests(
    project: str | Path,
    output_root: str | Path = "evidence",
    *,
    unity: str = "unity",
    mode: str = "EditMode",
    execute: bool = False,
    timeout_seconds: int = 600,
    runner: Run = subprocess.run,
) -> UnityBridgeResult:
    root, version = _project(project)
    if mode not in {"EditMode", "PlayMode"}:
        raise ValueError("mode must be EditMode or PlayMode")
    if not 1 <= timeout_seconds <= 3600:
        raise ValueError("timeout_seconds must be between 1 and 3600")
    executable = _cli(unity)
    destination = Path(output_root) / ADAPTER_ID / "test" / uuid.uuid4().hex
    report = destination / "nunit.xml"
    argv = [
        executable, "test", str(root), "--mode", mode, "--output", str(report.resolve()),
        "--timeout", str(timeout_seconds), "--format", "json", "--non-interactive",
    ]
    record: dict[str, Any] = {
        "schema_version": 1, "service": ADAPTER_ID, "engine": "unity",
        "project": str(root), "editor_version": version, "mode": mode,
        "evidence_class": "recorded_unity_cli_test" if execute else "unity_test_dry_run",
        "status": "HOLD", "verdict": "NOT_RUN", "plugin_installed": "unverified",
        "reason": "Unity tests alone do not prove running gameplay or authorize promotion",
        "planned_argv": argv,
    }
    if execute:
        destination.mkdir(parents=True, exist_ok=False)
        result = _invoke(argv, root, timeout_seconds + 30, runner)
        result.pop("response")
        valid, counts = _nunit_verdict(report)
        record["runner"] = result
        record["nunit_counts"] = counts
        record["report_sha256"] = _digest(report.read_bytes()) if report.is_file() else None
        record["verdict"] = "PASS" if valid and result["returncode"] == 0 else "FAIL"
    else:
        destination.mkdir(parents=True, exist_ok=False)
    path = destination / "evaluation.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return UnityBridgeResult(root=destination, status="HOLD", verdict=record["verdict"], evidence_path=path)
