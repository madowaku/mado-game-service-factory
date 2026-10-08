from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
from typing import Any, Callable, Sequence


REQUIRED_ACTIONS = (
    "scene_inspected",
    "compile_ok",
    "play_started",
    "input_simulated",
    "screenshot_captured",
    "logs_checked",
)


@dataclass(frozen=True)
class EdenSparkMission:
    mission_id: str
    title: str
    hypothesis: str
    success_criteria: tuple[str, ...]
    max_iterations: int = 3


@dataclass(frozen=True)
class EdenSparkEvaluation:
    root: Path
    status: str
    score: float
    evidence_class: str
    missing_actions: tuple[str, ...]
    artifact_count: int
    runtime_error_count: int


@dataclass(frozen=True)
class EdenSparkLoopResult:
    root: Path
    status: str
    iterations: int
    best_score: float
    final_evaluation: EdenSparkEvaluation | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_mission_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in value.strip())
    cleaned = cleaned.strip("-.")
    if not cleaned:
        raise ValueError("mission_id must contain at least one safe character")
    return cleaned


def load_mission(path: str | Path) -> EdenSparkMission:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise ValueError("mission schema_version must be 1")
    mission_id = _safe_mission_id(str(raw["mission_id"]))
    criteria = tuple(str(item).strip() for item in raw.get("success_criteria", []) if str(item).strip())
    if not criteria:
        raise ValueError("mission requires at least one success criterion")
    max_iterations = int(raw.get("max_iterations", 3))
    if not 1 <= max_iterations <= 10:
        raise ValueError("max_iterations must be between 1 and 10")
    return EdenSparkMission(
        mission_id=mission_id,
        title=str(raw["title"]).strip(),
        hypothesis=str(raw["hypothesis"]).strip(),
        success_criteria=criteria,
        max_iterations=max_iterations,
    )


def result_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "mission_id",
            "iteration",
            *REQUIRED_ACTIONS,
            "runtime_errors",
            "observations",
            "changed_files",
            "artifact_paths",
        ],
        "properties": {
            "mission_id": {"type": "string"},
            "iteration": {"type": "integer", "minimum": 1},
            **{name: {"type": "boolean"} for name in REQUIRED_ACTIONS},
            "runtime_errors": {"type": "array", "items": {"type": "string"}},
            "observations": {"type": "array", "items": {"type": "string"}},
            "changed_files": {"type": "array", "items": {"type": "string"}},
            "artifact_paths": {"type": "array", "items": {"type": "string"}},
        },
    }


def build_agent_prompt(mission: EdenSparkMission, iteration: int, prior: dict[str, Any] | None = None) -> str:
    criteria = "\n".join(f"- {item}" for item in mission.success_criteria)
    prior_text = ""
    if prior:
        prior_text = "\nPrevious iteration result:\n" + json.dumps(prior, indent=2, ensure_ascii=False)
    return f"""You are implementing and verifying an EdenSpark game prototype inside the current project.

Mission: {mission.title}
Hypothesis: {mission.hypothesis}
Iteration: {iteration}

Success criteria:
{criteria}

Use the EdenSpark MCP tools that are already configured for this project. Do not merely edit files and stop.
You must, in order where practical:
1. Inspect the current scene before making changes.
2. Implement the smallest change that tests the hypothesis.
3. Verify Daslang/editor compilation or hot reload succeeds.
4. Start or restart the game and verify it reaches playable state.
5. Simulate meaningful keyboard/mouse input through EdenSpark MCP.
6. Capture at least one screenshot through EdenSpark MCP and, when the tool supports a path, save it under .mgsf/artifacts/{mission.mission_id}/iteration-{iteration}/.
7. Read runtime/editor logs after playtesting and report any errors.
8. Keep changes reversible and do not publish or submit the project.

Return only data matching the provided JSON schema. artifact_paths must contain project-relative paths for any files you can actually preserve. Never invent an artifact path. If an MCP action is unavailable or failed, set the corresponding boolean false and explain in observations/runtime_errors.
{prior_text}
"""


def create_mission_pack(mission_path: str | Path, output_root: str | Path) -> Path:
    mission = load_mission(mission_path)
    root = Path(output_root) / mission.mission_id
    root.mkdir(parents=True, exist_ok=True)
    normalized = {
        "schema_version": 1,
        "mission_id": mission.mission_id,
        "title": mission.title,
        "hypothesis": mission.hypothesis,
        "success_criteria": list(mission.success_criteria),
        "max_iterations": mission.max_iterations,
    }
    (root / "mission.json").write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
    (root / "result-schema.json").write_text(json.dumps(result_schema(), indent=2), encoding="utf-8")
    (root / "PROMPT.md").write_text(build_agent_prompt(mission, 1), encoding="utf-8")
    return root


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_artifacts(project: Path, artifact_paths: Sequence[str]) -> tuple[list[dict[str, Any]], list[str]]:
    resolved: list[dict[str, Any]] = []
    invalid: list[str] = []
    project_resolved = project.resolve()
    for value in artifact_paths:
        rel = Path(value)
        if rel.is_absolute():
            invalid.append(value)
            continue
        candidate = (project / rel).resolve()
        try:
            candidate.relative_to(project_resolved)
        except ValueError:
            invalid.append(value)
            continue
        if not candidate.is_file():
            invalid.append(value)
            continue
        resolved.append(
            {
                "path": candidate.relative_to(project_resolved).as_posix(),
                "bytes": candidate.stat().st_size,
                "sha256": _hash_file(candidate),
            }
        )
    return resolved, invalid


def evaluate_result(
    project: str | Path,
    mission: EdenSparkMission,
    result_path: str | Path,
    output_root: str | Path,
    *,
    evidence_class: str,
    runner_record: dict[str, Any] | None = None,
) -> EdenSparkEvaluation:
    project_path = Path(project)
    result_file = Path(result_path)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    if data.get("mission_id") != mission.mission_id:
        raise ValueError("result mission_id does not match mission")

    missing = tuple(name for name in REQUIRED_ACTIONS if data.get(name) is not True)
    runtime_errors = [str(item) for item in data.get("runtime_errors", [])]
    artifacts, invalid_artifacts = _resolve_artifacts(project_path, data.get("artifact_paths", []))

    action_score = (len(REQUIRED_ACTIONS) - len(missing)) / len(REQUIRED_ACTIONS)
    artifact_score = 1.0 if artifacts else 0.0
    runtime_score = 1.0 if not runtime_errors else 0.0
    score = round((action_score * 0.7) + (artifact_score * 0.15) + (runtime_score * 0.15), 4)

    recorded_runner_ok = bool(
        runner_record
        and runner_record.get("runner") == "codex-exec"
        and runner_record.get("returncode") == 0
    )
    if evidence_class == "deterministic_edenspark_fixture":
        status = "HOLD"
        reason = "fixture evidence cannot promote an engine adapter"
    elif missing or runtime_errors or invalid_artifacts:
        status = "ITERATE"
        reason = "required live playtest evidence is incomplete"
    elif not artifacts:
        status = "ITERATE"
        reason = "no preserved artifact is available to verify the claimed visual check"
    elif not recorded_runner_ok:
        status = "HOLD"
        reason = "no successful MGSF codex-exec runner record accompanies the agent result"
    else:
        status = "PASS"
        reason = "recorded agent run satisfied the EdenSpark playtest contract"

    root = Path(output_root) / mission.mission_id / f"iteration-{int(data.get('iteration', 1))}"
    root.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": 1,
        "service": "edenspark-agent-adapter",
        "mission_id": mission.mission_id,
        "iteration": int(data.get("iteration", 1)),
        "evidence_class": evidence_class,
        "evaluated_at": _utc_now(),
        "status": status,
        "reason": reason,
        "score": score,
        "required_actions": {name: bool(data.get(name)) for name in REQUIRED_ACTIONS},
        "missing_actions": list(missing),
        "runtime_errors": runtime_errors,
        "invalid_artifacts": invalid_artifacts,
        "artifacts": artifacts,
        "observations": [str(item) for item in data.get("observations", [])],
        "changed_files": [str(item) for item in data.get("changed_files", [])],
        "runner": runner_record,
    }
    (root / "evaluation.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    return EdenSparkEvaluation(
        root=root,
        status=status,
        score=score,
        evidence_class=evidence_class,
        missing_actions=missing,
        artifact_count=len(artifacts),
        runtime_error_count=len(runtime_errors),
    )


def _default_codex_command(codex: str, schema_path: Path, answer_path: Path) -> list[str]:
    return [
        codex,
        "exec",
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(answer_path),
        "-",
    ]


def run_codex_iteration(
    project: str | Path,
    mission: EdenSparkMission,
    output_root: str | Path,
    *,
    iteration: int,
    codex: str = "codex",
    timeout_seconds: int = 1800,
    prior: dict[str, Any] | None = None,
    command_builder: Callable[[str, Path, Path], list[str]] = _default_codex_command,
) -> tuple[Path, dict[str, Any]]:
    project_path = Path(project)
    if not project_path.is_dir():
        raise FileNotFoundError(f"EdenSpark project not found: {project_path}")

    run_root = Path(output_root) / mission.mission_id / f"iteration-{iteration}" / "runner"
    run_root.mkdir(parents=True, exist_ok=True)
    schema_path = run_root / "result-schema.json"
    answer_path = run_root / "agent-result.json"
    prompt_path = run_root / "prompt.txt"
    stdout_path = run_root / "codex.stdout.txt"
    stderr_path = run_root / "codex.stderr.txt"
    schema_path.write_text(json.dumps(result_schema(), indent=2), encoding="utf-8")
    prompt = build_agent_prompt(mission, iteration, prior)
    prompt_path.write_text(prompt, encoding="utf-8")

    command = command_builder(codex, schema_path, answer_path)
    started_at = _utc_now()
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=os.environ.copy(),
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nMGSF timeout after {timeout_seconds}s"

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    runner = {
        "schema_version": 1,
        "runner": "codex-exec",
        "started_at": started_at,
        "finished_at": _utc_now(),
        "returncode": returncode,
        "command": [str(part) for part in command],
        "cwd": str(project_path.resolve()),
        "stdout_sha256": _hash_file(stdout_path),
        "stderr_sha256": _hash_file(stderr_path),
    }
    (run_root / "runner.json").write_text(json.dumps(runner, indent=2), encoding="utf-8")
    if not answer_path.is_file():
        failure = {
            "mission_id": mission.mission_id,
            "iteration": iteration,
            **{name: False for name in REQUIRED_ACTIONS},
            "runtime_errors": [f"Codex did not produce a structured result; returncode={returncode}"],
            "observations": ["See runner stdout/stderr evidence."],
            "changed_files": [],
            "artifact_paths": [],
        }
        answer_path.write_text(json.dumps(failure, indent=2), encoding="utf-8")
    return answer_path, runner


def run_autonomous_loop(
    project: str | Path,
    mission_path: str | Path,
    output_root: str | Path,
    *,
    codex: str = "codex",
    max_iterations: int | None = None,
    timeout_seconds: int = 1800,
) -> EdenSparkLoopResult:
    mission = load_mission(mission_path)
    limit = mission.max_iterations if max_iterations is None else max_iterations
    if not 1 <= limit <= 10:
        raise ValueError("max_iterations must be between 1 and 10")

    root = Path(output_root) / mission.mission_id
    root.mkdir(parents=True, exist_ok=True)
    previous: dict[str, Any] | None = None
    best = 0.0
    final: EdenSparkEvaluation | None = None

    iteration = 0
    for iteration in range(1, limit + 1):
        answer_path, runner = run_codex_iteration(
            project,
            mission,
            output_root,
            iteration=iteration,
            codex=codex,
            timeout_seconds=timeout_seconds,
            prior=previous,
        )
        previous = json.loads(answer_path.read_text(encoding="utf-8"))
        final = evaluate_result(
            project,
            mission,
            answer_path,
            output_root,
            evidence_class="recorded_edenspark_agent_mcp_run",
            runner_record=runner,
        )
        best = max(best, final.score)
        if final.status == "PASS":
            break

    status = final.status if final else "HOLD"
    summary = {
        "schema_version": 1,
        "service": "edenspark-autonomous-playtest",
        "mission_id": mission.mission_id,
        "status": status,
        "iterations": iteration if final else 0,
        "best_score": round(best, 4),
        "final_evaluation": str(final.root / "evaluation.json") if final else None,
    }
    (root / "loop-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return EdenSparkLoopResult(
        root=root,
        status=status,
        iterations=iteration if final else 0,
        best_score=best,
        final_evaluation=final,
    )
