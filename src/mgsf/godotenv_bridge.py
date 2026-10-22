"""MGSF-M1.2 safe bridge to Chickensoft GodotEnv.

Audits are local and read-only by default. Preparing a project requires
explicit consent because GodotEnv changes a user-wide symlink.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree

BRIDGE_ID = "godotenv-reproducible-environment"
VERSION = "1.2.0"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?$")
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class GodotEnvBridgeError(ValueError):
    """A project is unsafe or not reproducibly pinned."""


@dataclass(frozen=True)
class Audit:
    project: Path
    status: str
    evidence: dict[str, Any]
    evidence_path: Path | None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonc(text: str) -> Any:
    """JSONC lexer which preserves comment-like sequences inside strings."""
    out = []
    quoted = escaped = False
    i = 0
    while i < len(text):
        c = text[i]
        if quoted:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
            i += 1
        elif c == '"':
            quoted = True
            out.append(c)
            i += 1
        elif text[i:i + 2] == "//":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
        elif text[i:i + 2] == "/*":
            end = text.find("*/", i + 2)
            if end < 0:
                raise GodotEnvBridgeError("unclosed JSONC comment")
            out.extend("\n" for c in text[i:end + 2] if c == "\n")
            i = end + 2
        else:
            out.append(c)
            i += 1
    compact = "".join(out)
    result = []
    quoted = escaped = False
    for i, c in enumerate(compact):
        if quoted:
            result.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
            result.append(c)
        elif c == ",":
            remaining = compact[i + 1:].lstrip()
            if remaining and remaining[0] not in "}]":
                result.append(c)
        else:
            result.append(c)
    try:
        return json.loads("".join(result))
    except json.JSONDecodeError as exc:
        raise GodotEnvBridgeError("invalid addon manifest JSONC") from exc


def _pin(project: Path) -> tuple[str, bool, str, list[str]]:
    candidates: list[tuple[str, str, bool]] = []
    inputs: list[str] = []
    rc = project / ".godotrc"
    if rc.exists():
        lines = rc.read_text(encoding="utf-8").strip().splitlines()
        match = re.fullmatch(r"(\S+)(?:\s+(no-dotnet))?", lines[0]) if lines else None
        if match is None:
            raise GodotEnvBridgeError("invalid .godotrc")
        candidates.append((".godotrc", match.group(1), match.group(2) is not None))
        inputs.append(".godotrc")
    global_json = project / "global.json"
    if global_json.exists():
        inputs.append("global.json")
        try:
            payload = json.loads(global_json.read_text(encoding="utf-8"))
            sdk = payload.get("msbuild-sdks", {}).get("Godot.NET.Sdk")
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise GodotEnvBridgeError("invalid global.json") from exc
        if sdk is not None:
            if not isinstance(sdk, str):
                raise GodotEnvBridgeError("Godot.NET.Sdk must be a version string")
            candidates.append(("global.json", sdk, False))
    for csproj in sorted(project.glob("*.csproj")):
        inputs.append(csproj.name)
        try:
            root = ElementTree.parse(csproj).getroot()
        except ElementTree.ParseError as exc:
            raise GodotEnvBridgeError("invalid .csproj XML") from exc
        sdk = root.attrib.get("Sdk", "")
        if sdk.startswith("Godot.NET.Sdk/"):
            candidates.append((csproj.name, sdk.split("/", 1)[1], False))
        for node in root.iter():
            if node.tag.split("}")[-1] == "Sdk" and node.attrib.get("Name") == "Godot.NET.Sdk":
                candidates.append((csproj.name, node.attrib.get("Version", ""), False))
    if not candidates:
        raise GodotEnvBridgeError("missing project-local Godot version pin")
    if any(not SEMVER.fullmatch(version) for _, version, _ in candidates):
        raise GodotEnvBridgeError("invalid Godot version pin")
    if len({(v, mode) for _, v, mode in candidates}) != 1:
        raise GodotEnvBridgeError("conflicting Godot version pins")
    source, version, no_dotnet = candidates[0]
    return version, no_dotnet, source, inputs


def _addons(project: Path) -> tuple[list[dict[str, str]], list[str]]:
    paths = [p for p in (project / "addons.json", project / "addons.jsonc") if p.exists()]
    if len(paths) > 1:
        raise GodotEnvBridgeError("ambiguous duplicate addon manifest")
    if not paths:
        return [], []
    data = _jsonc(paths[0].read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("addons"), dict):
        raise GodotEnvBridgeError("addon manifest needs an addons object")
    if data.get("path", "addons") != "addons" or data.get("cache", ".addons") != ".addons":
        raise GodotEnvBridgeError("custom addon install/cache paths forbidden")
    result = []
    for name, entry in sorted(data["addons"].items()):
        if not isinstance(name, str) or name in (".", "..") or not SEGMENT.fullmatch(name):
            raise GodotEnvBridgeError("unsafe addon name")
        if not isinstance(entry, dict) or entry.get("source", "remote") != "remote":
            raise GodotEnvBridgeError("only pinned remote git addons supported")
        url = entry.get("url")
        if not isinstance(url, str):
            raise GodotEnvBridgeError("addon missing URL")
        try:
            address = urlsplit(url)
            port = address.port
        except ValueError as exc:
            raise GodotEnvBridgeError("invalid addon URL") from exc
        if (address.scheme != "https" or address.hostname != "github.com" or
            address.username or address.password or port or address.query or
            address.fragment or not re.fullmatch(
                r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?", address.path
            )):
            raise GodotEnvBridgeError("addon requires HTTPS GitHub URL")
        checkout = entry.get("checkout")
        if not isinstance(checkout, str) or not SHA.fullmatch(checkout):
            raise GodotEnvBridgeError("addon checkout requires full 40-character commit SHA")
        subfolder = entry.get("subfolder", "/")
        if not isinstance(subfolder, str) or (subfolder != "/" and (
            not subfolder or subfolder.startswith("/") or "\\" in subfolder or
            any(part in (".", "..") or not SEGMENT.fullmatch(part)
                for part in subfolder.split("/"))
        )):
            raise GodotEnvBridgeError("unsafe addon subfolder")
        result.append({"name": name, "url": url, "checkout": checkout.lower(),
                       "subfolder": subfolder})
    return result, [paths[0].name]


def _plan(version: str, no_dotnet: bool, install_addons: bool) -> list[list[str]]:
    mode = ["--no-dotnet"] if no_dotnet else []
    commands = [["godotenv", "godot", "install", version, *mode],
                ["godotenv", "godot", "use", version, *mode]]
    if install_addons:
        commands.append(["godotenv", "addons", "install"])
    return commands


def _store(root: Path | None, record: dict[str, Any]) -> Path | None:
    if root is None:
        return None
    path = Path(root) / BRIDGE_ID / "audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _exec(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, check=False, shell=False)


def audit_project(project: Path | str, output_root: Path | None = None, *,
                  probe: bool = False, executable: str = "godotenv") -> Audit:
    project = Path(project).resolve()
    record: dict[str, Any] = {
        "bridge": BRIDGE_ID, "version": VERSION, "project": str(project),
        "evidence_class": "static_project_audit", "status": "HOLD",
        "tool": {"name": "Chickensoft.GodotEnv", "recommended_version": "2.17.0"},
        "warnings": [], "errors": [], "criteria": {}, "input_sha256": {},
        "addons": [], "commands": [],
    }
    problems = record["errors"]
    if not (project / "project.godot").is_file() or (project / "project.godot").is_symlink():
        problems.append("project.godot missing or symlinked")
    else:
        try:
            version, no_dotnet, pin_source, pin_files = _pin(project)
            addons, addon_files = _addons(project)
            for name in ("project.godot", *pin_files, *addon_files):
                path = project / name
                if path.is_symlink():
                    raise GodotEnvBridgeError("symlinked config input forbidden")
                record["input_sha256"][name] = _sha(path)
            record["pin"] = {"version": version, "no_dotnet": no_dotnet,
                             "source": pin_source}
            record["addons"] = addons
            record["commands"] = _plan(version, no_dotnet, bool(addons))
        except (GodotEnvBridgeError, OSError, UnicodeError) as exc:
            problems.append(str(exc))
    record["criteria"]["static_manifest_safe"] = not problems
    if probe and not problems:
        record["evidence_class"] = "live_environment_probe"
        tool = shutil.which(executable)
        if not tool:
            record["warnings"].append("godotenv tool missing")
        else:
            try:
                target = _exec([tool, "godot", "env", "target"], project, 15)
                if target.returncode != 0:
                    record["warnings"].append("GodotEnv cannot report active target")
                else:
                    exe = Path(target.stdout.strip().strip('"'))
                    if not exe.is_file():
                        record["warnings"].append("active Godot target is missing")
                    else:
                        check = _exec([str(exe), "--version"], project, 15)
                        actual = check.stdout.strip().splitlines()[0] if check.stdout.strip() else ""
                        expected = record["pin"]["version"]
                        matches = check.returncode == 0 and (
                            actual == expected or actual.startswith(expected + ".") or
                            actual.startswith(expected + "-")
                        )
                        record["criteria"]["active_version_matches_pin"] = matches
                        record["probe"] = {
                            "active_target": str(exe), "reported_version": actual,
                            "returncode": check.returncode, "version_matches_pin": matches,
                        }
                        if not matches:
                            problems.append("active Godot version does not match pin")
            except (OSError, subprocess.TimeoutExpired) as exc:
                record["warnings"].append("GodotEnv probe failed: " + type(exc).__name__)
    if problems:
        record["status"] = "FAIL"
    elif probe and record["criteria"].get("active_version_matches_pin"):
        if record["addons"]:
            record["warnings"].append("pinned addons need explicit verified installation")
        else:
            record["status"] = "PASS"
    return Audit(project, record["status"], record, _store(output_root, record))


def prepare_project(project: Path | str, output_root: Path, *,
                    allow_global_switch: bool = False, install_addons: bool = False,
                    executable: str = "godotenv") -> Audit:
    audit = audit_project(project)
    record = audit.evidence
    record["evidence_class"] = "opt_in_godotenv_execution"
    record["executed"] = []
    if audit.status == "FAIL":
        return Audit(audit.project, "FAIL", record, _store(output_root, record))
    if not allow_global_switch:
        record["warnings"].append("--allow-global-switch not provided; no change made")
        return Audit(audit.project, "HOLD", record, _store(output_root, record))
    if install_addons:
        if not record["addons"]:
            record["errors"].append("no pinned addons declared")
        for name in ("addons", ".addons"):
            folder = audit.project / name
            if folder.exists() or folder.is_symlink():
                record["errors"].append("refusing to overwrite existing addons/.addons")
    tool = shutil.which(executable)
    if not tool:
        record["errors"].append("godotenv executable missing")
    if record["errors"]:
        record["status"] = "FAIL"
        return Audit(audit.project, "FAIL", record, _store(output_root, record))
    try:
        for argv in _plan(record["pin"]["version"], record["pin"]["no_dotnet"],
                          install_addons):
            argv[0] = tool
            outcome = _exec(argv, audit.project, 120 if argv[1] == "addons" else 300)
            record["executed"].append({
                "argv": argv[1:], "returncode": outcome.returncode,
                "stdout_tail": outcome.stdout[-2000:], "stderr_tail": outcome.stderr[-2000:],
            })
            if outcome.returncode:
                record["errors"].append("GodotEnv command failed")
                break
    except (OSError, subprocess.TimeoutExpired) as exc:
        record["errors"].append("execution interrupted: " + type(exc).__name__)
    if not record["errors"] and install_addons:
        snapshots = {}
        for item in record["addons"]:
            folder = audit.project / "addons" / item["name"]
            if not folder.is_dir() or folder.is_symlink():
                record["errors"].append("installed addon missing")
                continue
            files = sorted(p for p in folder.rglob("*") if p.is_file())
            if not files or any(p.is_symlink() for p in files):
                record["errors"].append("invalid installed addon contents")
                continue
            snapshots[item["name"]] = {
                str(path.relative_to(folder)): _sha(path) for path in files
            }
        record["installed_addon_files_sha256"] = snapshots
    if not record["errors"]:
        live = audit_project(audit.project, probe=True, executable=executable)
        observed = live.evidence["criteria"].get("active_version_matches_pin", False)
        record["criteria"]["active_version_matches_pin"] = observed
        record["probe"] = live.evidence.get("probe")
        if not observed:
            record["errors"].append("post-apply engine version verification failed")
    record["status"] = ("FAIL" if record["errors"] else
                        "HOLD" if record["addons"] and not install_addons else "PASS")
    if record["status"] == "HOLD":
        record["warnings"].append("addon installation was not verified")
    return Audit(audit.project, record["status"], record, _store(output_root, record))
