"""Safe Godogen intake, Codex loop, and provenance-gated visual proof for MGSF M0.9.

Godogen is a local, pinned upstream source checkout. We never execute its
publish.sh, install hooks, enable paid asset services, or overwrite a project.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

ENGINE = "godot"
SOURCE_FILES = ("prompts/runtime.md", "engines/godot.md", "LICENSE.md")
MAX_INTAKE_BYTES = 16 * 1024 * 1024
MAX_MEDIA_BYTES = 100 * 1024 * 1024
RESULT_FIELDS = (
    "build_ok", "runtime_started", "input_simulated",
    "gameplay_observed", "video_reviewed",
)


class GodogenError(ValueError):
    """Unsafe intake or invalid proof contract."""


@dataclass(frozen=True)
class GodogenEvaluation:
    root: Path
    status: str
    reason: str
    artifact_count: int


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _git(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        text=True, capture_output=True, check=False, timeout=30,
    )
    if result.returncode:
        raise GodogenError("could not verify local Godogen Git checkout")
    return result.stdout.strip()


def _plain_files(directory: Path) -> list[Path]:
    if not directory.is_dir() or directory.is_symlink():
        raise GodogenError("asset-gen must be a real directory")
    found: list[Path] = []
    for entry in sorted(directory.rglob("*")):
        if entry.is_symlink() or (not entry.is_file() and not entry.is_dir()):
            raise GodogenError("symlinks and special files are forbidden in upstream")
        if entry.is_file():
            if any(part.startswith(".") for part in entry.relative_to(directory).parts):
                raise GodogenError("hidden upstream files are not allowed")
            found.append(entry)
    if not any(p.name == "SKILL.md" and p.parent == directory for p in found):
        raise GodogenError("Godogen asset-gen/SKILL.md is required")
    return found


def intake_godogen(
    source: str | Path, target: str | Path, expected_sha: str, *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview, or safely stage, one isolated Codex/Godot runtime."""
    src = Path(source).resolve()
    dst = Path(target).resolve()
    if not src.is_dir() or not re.fullmatch(r"[a-fA-F0-9]{40}", expected_sha):
        raise GodogenError("source checkout and 40-character expected_sha are required")
    if dst == src or src in dst.parents or dst in src.parents:
        raise GodogenError("source and target must be disjoint")
    if dst.exists():
        raise GodogenError("target already exists; refusing to overwrite")
    if _git(src, "rev-parse", "--show-toplevel") != str(src):
        raise GodogenError("source must be the Godogen repository root")
    origin = _git(src, "remote", "get-url", "origin")
    trusted_origins = {
        "https://github.com/htdt/godogen",
        "https://github.com/htdt/godogen.git",
        "git@github.com:htdt/godogen",
        "git@github.com:htdt/godogen.git",
        "ssh://git@github.com/htdt/godogen.git",
    }
    if origin not in trusted_origins:
        raise GodogenError("upstream origin must be htdt/godogen")
    head = _git(src, "rev-parse", "HEAD")
    if head.lower() != expected_sha.lower():
        raise GodogenError("upstream HEAD is not the pinned expected_sha")
    if _git(src, "status", "--porcelain", "--untracked-files=all"):
        raise GodogenError("upstream checkout must be clean")
    inputs = [src / name for name in SOURCE_FILES]
    for path in inputs:
        if not path.is_file() or path.is_symlink():
            raise GodogenError(f"missing or unsafe upstream file: {path.name}")
    inputs += _plain_files(src / "asset-gen")
    if len(inputs) > 200 or sum(p.stat().st_size for p in inputs) > MAX_INTAKE_BYTES:
        raise GodogenError("upstream source exceeds intake bounds")
    manifest = {
        "schema_version": 1,
        "service": "godogen-adapter",
        "upstream": "htdt/godogen",
        "upstream_sha": head,
        "engine": ENGINE,
        "agent": "codex",
        "source_files": {p.relative_to(src).as_posix(): _sha(p) for p in inputs},
        "policy": {
            "isolated_new_directory": True,
            "upstream_publish_script_executed": False,
            "paid_asset_generation_enabled": False,
            "fixture_is_not_live_proof": True,
        },
    }
    if dry_run:
        return {"status": "PREVIEW", "target": str(dst), **manifest}

    dst.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".mgsf-godogen-", dir=dst.parent))
    try:
        paths = {
            "prompts/runtime.md": "AGENTS.md",
            "engines/godot.md": "godot.md",
            "LICENSE.md": ".mgsf/upstream/LICENSE.md",
        }
        replacements = {
            "ENGINE_NAME": "Godot",
            "ENGINE_GUIDE_FILE": "godot.md",
            "ASSET_SKILL_COMMAND": "$asset-gen",
            "ASSET_GEN_SKILL_DIR": ".agents/skills/asset-gen",
            "AGENT_NAME": "Codex",
            "RUNTIME_ASSET_DIR": "assets",
        }
        for path in inputs:
            rel = path.relative_to(src).as_posix()
            dest = staging / paths.get(rel, ".agents/skills/" + rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                dest.write_bytes(raw)
            else:
                for key, value in replacements.items():
                    text = text.replace("$" + "{" + key + "}", value)
                dest.write_text(text, encoding="utf-8")
        if not (staging / ".agents/skills/asset-gen/SKILL.md").is_file():
            raise GodogenError("asset skill was not staged")
        manifest["staged_files"] = {
            name: _sha(staging / name) for name in
            ("AGENTS.md", "godot.md", ".agents/skills/asset-gen/SKILL.md")
        }
        _json(staging / ".mgsf/godogen-intake.json", manifest)
        if dst.exists():
            raise GodogenError("target appeared during intake; refusing overwrite")
        staging.rename(dst)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"status": "STAGED", "target": str(dst), **manifest}


def load_mission(path: str | Path) -> dict[str, Any]:
    mission = json.loads(Path(path).read_text(encoding="utf-8"))
    if mission.get("schema_version") != 1:
        raise GodogenError("mission schema_version must equal 1")
    value = mission.get("mission_id")
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", value):
        raise GodogenError("invalid mission_id")
    if not isinstance(mission.get("description"), str) or not mission["description"].strip():
        raise GodogenError("mission description must not be empty")
    criteria = mission.get("success_criteria")
    if not isinstance(criteria, list) or not criteria or any(not isinstance(x, str) or not x.strip() for x in criteria):
        raise GodogenError("mission needs nonempty success_criteria strings")
    count = mission.get("max_iterations", 2)
    if type(count) is not int or not 1 <= count <= 3:
        raise GodogenError("max_iterations must be an integer from 1 to 3")
    return {**mission, "max_iterations": count}


def result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["mission_id", *RESULT_FIELDS, "runtime_errors", "observations", "proof_video"],
        "properties": {
            "mission_id": {"type": "string"},
            **{name: {"type": "boolean"} for name in RESULT_FIELDS},
            "runtime_errors": {"type": "array", "items": {"type": "string"}},
            "observations": {"type": "array", "items": {"type": "string"}},
            "proof_video": {"type": "string"},
        },
    }


def _safe_artifact(project: Path, value: str) -> Path | None:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    root = project.resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() != ".mp4":
        return None
    if path.stat().st_size == 0 or path.stat().st_size > MAX_MEDIA_BYTES:
        return None
    return path


def _verify_video(path: Path, ffprobe: str) -> tuple[bool, dict[str, Any]]:
    try:
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=False, timeout=20,
        )
        data = json.loads(probe.stdout) if probe.returncode == 0 else {}
        streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        duration = float(data.get("format", {}).get("duration", 0))
        ok = (14 <= duration <= 22 and any(
            int(s.get("width") or 0) >= 320 and int(s.get("height") or 0) >= 180 for s in streams
        ))
        return ok, {"duration_seconds": duration, "streams": streams}
    except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False, {}


def evaluate_godogen(
    project: str | Path, mission: dict[str, Any], result_path: str | Path,
    runner_record: dict[str, Any] | None, output_root: str | Path, *,
    fixture: bool = False, ffprobe: str = "ffprobe", iteration: int = 1,
) -> GodogenEvaluation:
    root_project = Path(project).resolve()
    data = json.loads(Path(result_path).read_text(encoding="utf-8"))
    if data.get("mission_id") != mission["mission_id"]:
        raise GodogenError("mission id mismatch")
    claimed = {key: data.get(key) is True for key in RESULT_FIELDS}
    errors = data.get("runtime_errors", [])
    if not isinstance(errors, list) or not all(isinstance(x, str) for x in errors):
        raise GodogenError("runtime_errors must be an array of strings")
    artifact = _safe_artifact(root_project, data.get("proof_video", ""))
    video_ok, video_info = _verify_video(artifact, ffprobe) if artifact else (False, {})
    godot_project = (root_project / "project.godot").is_file() and any(root_project.glob("*.csproj"))
    steps = (runner_record or {}).get("engine_checks", {})
    runner_ok = (runner_record or {}).get("runner") == "codex-exec" and (runner_record or {}).get("returncode") == 0
    engine_ok = all(isinstance(steps.get(key), dict) and steps[key].get("returncode") == 0
                    for key in ("dotnet_build", "godot_import", "godot_launch"))
    checks = {
        "agent_actions": all(claimed.values()),
        "no_reported_errors": not errors,
        "godot_project_exists": bool(godot_project),
        "codex_runner_success": runner_ok,
        "independent_engine_checks": engine_ok,
        "valid_15_to_20_second_video": video_ok,
    }
    # 14-22 seconds is an encoding tolerance around the requested 15-20s clip.
    if fixture:
        status, reason = "HOLD", "deterministic fixture is never live engine proof"
    elif not runner_ok or not engine_ok:
        status, reason = "HOLD", "recorded Codex run and independent engine checks are required"
    elif all(checks.values()):
        status, reason = "PASS", "recorded Codex run, engine probes, and verified video satisfy the contract"
    else:
        status, reason = "ITERATE", "gameplay proof contract is incomplete"

    root = Path(output_root) / mission["mission_id"] / f"iteration-{iteration}"
    root.mkdir(parents=True, exist_ok=True)
    media = []
    if artifact and video_ok:
        preserved = root / "proof.mp4"
        if artifact.resolve() != preserved.resolve():
            shutil.copyfile(artifact, preserved)
        media = [{"path": "proof.mp4", "sha256": _sha(preserved), "bytes": preserved.stat().st_size,
                  "source_relative_path": artifact.relative_to(root_project).as_posix(),
                  "probe": video_info}]
    provenance_file = root_project / ".mgsf/godogen-intake.json"
    provenance = json.loads(provenance_file.read_text(encoding="utf-8")) if provenance_file.is_file() else {}
    _json(root / "evaluation.json", {
        "schema_version": 1, "service": "godogen-adapter",
        "upstream_sha": provenance.get("upstream_sha"),
        "mission_id": mission["mission_id"], "engine": ENGINE, "iteration": iteration,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_class": "deterministic_godogen_fixture" if fixture else "recorded_godogen_codex_run",
        "status": status, "reason": reason, "score": round(sum(checks.values()) / len(checks), 4),
        "checks": checks, "claims": claimed, "runtime_errors": errors,
        "video": media, "runner": runner_record,
        "provenance_note": "Agent-mediated game proof, not a human playtest or independent gameplay-quality score.",
    })
    return GodogenEvaluation(root, status, reason, len(media))


def _run_step(argv: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return {"command": argv, "returncode": p.returncode,
                "stdout_sha256": sha256(p.stdout.encode()).hexdigest(),
                "stderr_sha256": sha256(p.stderr.encode()).hexdigest(),
                "stderr_tail": p.stderr[-1500:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": argv, "returncode": 124, "error": str(exc)}


def run_godogen_loop(
    project: str | Path, mission_path: str | Path, output_root: str | Path, *,
    codex: str = "codex", godot: str = "godot", dotnet: str = "dotnet",
    ffprobe: str = "ffprobe", timeout_seconds: int = 1800,
) -> GodogenEvaluation:
    project = Path(project).resolve()
    manifest_file = project / ".mgsf/godogen-intake.json"
    if not manifest_file.is_file():
        raise GodogenError("run requires an isolated MGSF-staged Godogen project")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("upstream") != "htdt/godogen" or manifest.get("engine") != ENGINE:
        raise GodogenError("invalid Godogen intake manifest")
    staged_hashes = manifest.get("staged_files")
    if not isinstance(staged_hashes, dict) or not staged_hashes:
        raise GodogenError("missing staged-file provenance")
    for relative, digest in staged_hashes.items():
        if relative not in ("AGENTS.md", "godot.md", ".agents/skills/asset-gen/SKILL.md"):
            raise GodogenError("unexpected staged-file entry")
        file = project / relative
        if not file.is_file() or file.is_symlink() or _sha(file) != digest:
            raise GodogenError("staged Godogen instructions changed after intake")
    if not 1 <= timeout_seconds <= 7200:
        raise GodogenError("timeout_seconds must be between 1 and 7200")
    mission = load_mission(mission_path)
    prior = None
    last = None
    for iteration in range(1, mission["max_iterations"] + 1):
        run_root = Path(output_root) / mission["mission_id"] / f"iteration-{iteration}" / "runner"
        run_root.mkdir(parents=True, exist_ok=True)
        schema_path = run_root / "schema.json"
        answer_path = run_root / "answer.json"
        _json(schema_path, result_schema())
        prompt = (
            "Build a Godot 4 .NET/C# game from this mission in the current Godogen project.\n"
            "Read AGENTS.md and godot.md first. Never publish, delete outside this project, "
            "or make paid API calls. No paid assets have been approved.\n"
            "Run dotnet build, import and launch Godot, drive meaningful gameplay input, "
            "record a 15-20 second game clip at screenshots/proof.mp4 and review the clip. "
            "If a step fails, report false; never invent proof. Keep proof_video project-relative.\n"
            + json.dumps(mission, ensure_ascii=False) + "\nPrior feedback: "
            + json.dumps(prior, ensure_ascii=False)
        )
        (run_root / "prompt.txt").write_text(prompt, encoding="utf-8")
        env = os.environ.copy()
        for key in ("GOOGLE_API_KEY", "XAI_API_KEY", "TRIPO_API_KEY"):
            env.pop(key, None)
        command = [codex, "exec", "--sandbox", "workspace-write",
                   "--output-schema", str(schema_path),
                   "--output-last-message", str(answer_path), "-"]
        started = datetime.now(timezone.utc).isoformat()
        try:
            result = subprocess.run(command, input=prompt, text=True, capture_output=True,
                                    cwd=project, timeout=timeout_seconds, check=False, env=env)
            code, stdout, stderr = result.returncode, result.stdout, result.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            code, stdout, stderr = 124, "", str(exc)
        (run_root / "stdout.txt").write_text(stdout, encoding="utf-8")
        (run_root / "stderr.txt").write_text(stderr, encoding="utf-8")
        checks = {
            "dotnet_build": _run_step([dotnet, "build"], project, 180),
            "godot_import": _run_step([godot, "--headless", "--path", str(project), "--import"], project, 120),
            "godot_launch": _run_step([godot, "--headless", "--path", str(project), "--quit-after", "5"], project, 120),
        } if code == 0 else {}
        runner = {
            "runner": "codex-exec", "returncode": code, "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "command": command, "cwd": str(project),
            "stdout_sha256": _sha(run_root / "stdout.txt"),
            "stderr_sha256": _sha(run_root / "stderr.txt"),
            "engine_checks": checks,
        }
        _json(run_root / "runner.json", runner)
        try:
            output = json.loads(answer_path.read_text(encoding="utf-8"))
            if not isinstance(output, dict) or output.get("mission_id") != mission["mission_id"]:
                raise ValueError("Codex result has an incorrect mission id")
        except (OSError, ValueError, json.JSONDecodeError):
            if answer_path.is_file():
                (run_root / "invalid-answer.txt").write_bytes(answer_path.read_bytes())
            _json(answer_path, {
                "mission_id": mission["mission_id"], **{key: False for key in RESULT_FIELDS},
                "runtime_errors": ["Codex did not produce a valid structured mission result"],
                "observations": [], "proof_video": "",
            })
        last = evaluate_godogen(project, mission, answer_path, runner, output_root,
                                ffprobe=ffprobe, iteration=iteration)
        if last.status == "PASS":
            return last
        prior = json.loads((last.root / "evaluation.json").read_text(encoding="utf-8"))
    assert last is not None
    return last
