"""Evidence-gated Godot replay, metrics, and before/after refinement.

Deterministic replay is not an autonomous AI player or a human playtest.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import re
import shutil
import subprocess
import os
from uuid import uuid4
from typing import Any

SCHEMA_VERSION = 1
EVIDENCE_FIXTURE = "deterministic_playtest_fixture"
EVIDENCE_LIVE = "recorded_godot_playtest"
_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


class PlaytestLabError(ValueError):
    """Invalid, incomplete, or incompatible playtest evidence."""


@dataclass(frozen=True)
class LabResult:
    root: Path
    status: str
    report_path: Path


def _json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlaytestLabError(f"invalid JSON: {path}") from exc
    if not isinstance(obj, dict):
        raise PlaytestLabError(f"expected object: {path}")
    return obj


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_scenario(path: str | Path) -> dict[str, Any]:
    data = _json(Path(path))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise PlaytestLabError("scenario schema_version must equal 1")
    if not isinstance(data.get("scenario_id"), str) or not _ID.fullmatch(data["scenario_id"]):
        raise PlaytestLabError("invalid scenario_id")
    if not isinstance(data.get("scene"), str) or not data["scene"].startswith("res://") or ".." in data["scene"].split("/"):
        raise PlaytestLabError("scene must be a project-relative res:// path")
    if not isinstance(data.get("state_node"), str) or not data["state_node"] or data["state_node"].startswith("/"):
        raise PlaytestLabError("state_node must be a scene-relative node path")
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 300:
        raise PlaytestLabError("steps must contain 1..300 actions")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("action"), str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", step["action"]):
            raise PlaytestLabError(f"invalid action at step {index}")
        if type(step.get("frames")) is not int or not 1 <= step["frames"] <= 600:
            raise PlaytestLabError(f"frames out of bounds at step {index}")
    limits = data.get("limits")
    if not isinstance(limits, dict):
        raise PlaytestLabError("scenario limits must be an object")
    for key in ("max_stalls", "max_deaths", "max_retries"):
        if type(limits.get(key)) is not int or not 0 <= limits[key] <= 100000:
            raise PlaytestLabError(f"invalid limits.{key}")
    return data


def _trace(path: Path) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise PlaytestLabError(f"invalid trace.jsonl: {path}") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise PlaytestLabError("trace rows must be objects")
    return rows


def _state_number(row: dict[str, Any], key: str) -> float:
    value = row["state"].get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -1e9 <= value <= 1e9:
        raise PlaytestLabError(f"state.{key} must be a finite number")
    return float(value)


def evaluate_session(session_root: str | Path) -> LabResult:
    root = Path(session_root)
    scenario_path = root / "scenario.json"
    scenario = load_scenario(scenario_path)
    session = _json(root / "session.json")
    if session.get("schema_version") != SCHEMA_VERSION or session.get("scenario_id") != scenario["scenario_id"]:
        raise PlaytestLabError("session/scenario identity mismatch")
    evidence_class = session.get("evidence_class")
    if evidence_class not in (EVIDENCE_FIXTURE, EVIDENCE_LIVE):
        raise PlaytestLabError("unknown evidence_class")
    if not isinstance(session.get("persona"), str) or not _ID.fullmatch(session["persona"]):
        raise PlaytestLabError("invalid persona")
    if session.get("driver") not in ("scripted_replay", "agent_authored_replay"):
        raise PlaytestLabError("driver must identify scripted or agent-authored replay")

    rows = _trace(root / "trace.jsonl")
    if len(rows) != len(scenario["steps"]):
        raise PlaytestLabError("trace must contain exactly one state per scenario step")
    for index, (row, step) in enumerate(zip(rows, scenario["steps"])):
        if type(row.get("step")) is not int or row["step"] != index:
            raise PlaytestLabError(f"non-contiguous step at index {index}")
        if row.get("action") != step["action"] or row.get("frames") != step["frames"]:
            raise PlaytestLabError(f"replay diverged from scenario at step {index}")
        state = row.get("state")
        if not isinstance(state, dict) or type(state.get("won")) is not bool:
            raise PlaytestLabError(f"invalid state at step {index}")
        for key in ("progress", "deaths", "retries"):
            _state_number(row, key)
        if not isinstance(row.get("errors"), list) or not all(isinstance(e, str) for e in row["errors"]):
            raise PlaytestLabError(f"invalid errors at step {index}")
    for previous, current in zip(rows, rows[1:]):
        if _state_number(current, "deaths") < _state_number(previous, "deaths") or _state_number(current, "retries") < _state_number(previous, "retries"):
            raise PlaytestLabError("cumulative deaths/retries cannot decrease")

    stalls = sum(_state_number(cur, "progress") <= _state_number(prev, "progress") for prev, cur in zip(rows, rows[1:]))
    deaths = _state_number(rows[-1], "deaths")
    retries = _state_number(rows[-1], "retries")
    won = any(row["state"]["won"] for row in rows)
    errors = [e for row in rows for e in row["errors"]]
    if evidence_class == EVIDENCE_LIVE:
        # Godot can report script/runtime failures despite a zero exit code.
        for log_name in ("godot.stdout.txt", "godot.stderr.txt"):
            log_path = root / log_name
            if log_path.is_file():
                errors.extend(line for line in log_path.read_text(encoding="utf-8").splitlines()
                              if re.search(r"\b(?:script error|error)\s*:|MGSF_PLAYTEST_ERROR", line, re.IGNORECASE))
    limits = scenario["limits"]
    metrics = {"goal_reached": won, "stall_transitions": stalls, "deaths": deaths,
               "retries": retries, "frames": sum(row["frames"] for row in rows), "runtime_errors": len(errors)}
    runner_ok = False
    runner_evidence: dict[str, Any] | None = None
    if evidence_class == EVIDENCE_LIVE:
        runner = _json(root / "runner.json")
        runner_ok = (
            runner.get("runner") == "godot-headless-script"
            and runner.get("returncode") == 0
            and runner.get("trace_sha256") == _sha(root / "trace.jsonl")
            and runner.get("scenario_sha256") == _sha(scenario_path)
            and runner.get("stdout_sha256") == _sha(root / "godot.stdout.txt")
            and runner.get("stderr_sha256") == _sha(root / "godot.stderr.txt")
            and "MGSF_PLAYTEST_OK" in (root / "godot.stdout.txt").read_text(encoding="utf-8")
            and isinstance(session.get("source_head_sha"), str)
            and bool(_SHA.fullmatch(session["source_head_sha"]))
        )
        runner_evidence = {"runner": runner.get("runner"), "returncode": runner.get("returncode"), "verified": runner_ok}
    criteria = {
        "goal_reached": won,
        "stall_budget": stalls <= limits["max_stalls"],
        "death_budget": deaths <= limits["max_deaths"],
        "retry_budget": retries <= limits["max_retries"],
        "no_runtime_errors": not errors,
        "runner_evidence_verified": runner_ok,
    }
    status = "HOLD" if evidence_class == EVIDENCE_FIXTURE else "PASS" if all(criteria.values()) else "ITERATE"
    report = {
        "schema_version": SCHEMA_VERSION,
        "service": "ai-playtest-laboratory",
        "scenario_id": scenario["scenario_id"],
        "persona": session["persona"],
        "driver": session["driver"],
        "source_head_sha": session.get("source_head_sha"),
        "evidence_class": evidence_class,
        "status": status,
        "criteria": criteria,
        "metrics": metrics,
        "errors": errors,
        "scenario_sha256": _sha(scenario_path),
        "trace_sha256": _sha(root / "trace.jsonl"),
        "runner_evidence": runner_evidence,
        "limitations": "Measured state metrics are not human fun, usability, or enjoyment scores.",
    }
    target = root / "evaluation.json"
    _write(target, report)
    return LabResult(root, status, target)


def compare_sessions(before_root: str | Path, after_root: str | Path, output_root: str | Path) -> LabResult:
    before_result = evaluate_session(before_root)
    after_result = evaluate_session(after_root)
    before = _json(before_result.report_path)
    after = _json(after_result.report_path)
    if before["scenario_id"] != after["scenario_id"] or before["persona"] != after["persona"]:
        raise PlaytestLabError("comparison requires same scenario and persona")
    if before["scenario_sha256"] != after["scenario_sha256"]:
        raise PlaytestLabError("scenario changed; comparable inputs are required")
    if before["driver"] != after["driver"]:
        raise PlaytestLabError("comparison requires the same replay driver")
    lower_better = ("stall_transitions", "deaths", "retries", "runtime_errors")
    regressions = [key for key in lower_better if after["metrics"][key] > before["metrics"][key]]
    if before["metrics"]["goal_reached"] and not after["metrics"]["goal_reached"]:
        regressions.append("goal_reached")
    improvements = [key for key in lower_better if after["metrics"][key] < before["metrics"][key]]
    if not before["metrics"]["goal_reached"] and after["metrics"]["goal_reached"]:
        improvements.append("goal_reached")
    if before["evidence_class"] != EVIDENCE_LIVE or after["evidence_class"] != EVIDENCE_LIVE or not before["criteria"]["runner_evidence_verified"] or not after["criteria"]["runner_evidence_verified"]:
        decision = "HOLD"
    elif regressions:
        decision = "REGRESSION"
    elif after["status"] != "PASS":
        decision = "ITERATE"
    elif improvements:
        decision = "IMPROVED"
    else:
        decision = "UNCHANGED"
    report = {
        "schema_version": SCHEMA_VERSION,
        "service": "ai-playtest-laboratory",
        "scenario_id": before["scenario_id"],
        "persona": before["persona"],
        "status": decision,
        "improvements": improvements,
        "regressions": regressions,
        "before": {"source_head_sha": before["source_head_sha"], "status": before["status"], "metrics": before["metrics"], "trace_sha256": before["trace_sha256"]},
        "after": {"source_head_sha": after["source_head_sha"], "status": after["status"], "metrics": after["metrics"], "trace_sha256": after["trace_sha256"]},
        "promotion_allowed": decision == "IMPROVED",
        "limitations": "No human experience or subjective fun measurement is inferred.",
    }
    target_root = Path(output_root) / before["scenario_id"] / "comparison"
    _write(target_root / "comparison.json", report)
    return LabResult(target_root, decision, target_root / "comparison.json")


def _git_sha(project: Path) -> str:
    try:
        p = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=True)
        return p.stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def run_godot_session(project: str | Path, scenario_path: str | Path, *, godot: str, output_root: str | Path,
                      persona: str = "qa", driver: str = "scripted_replay", timeout_seconds: int = 120,
                      source_head_sha: str | None = None) -> LabResult:
    project_path = Path(project).resolve()
    scenario_source = Path(scenario_path).resolve()
    scenario = load_scenario(scenario_source)
    if not (project_path / "project.godot").is_file():
        raise PlaytestLabError("project.godot not found")
    if not isinstance(persona, str) or not _ID.fullmatch(persona):
        raise PlaytestLabError("invalid persona")
    if driver not in ("scripted_replay", "agent_authored_replay"):
        raise PlaytestLabError("invalid driver")
    if not 1 <= timeout_seconds <= 3600:
        raise PlaytestLabError("timeout_seconds out of bounds")
    executable = shutil.which(godot) or (str(Path(godot).resolve()) if Path(godot).is_file() else None)
    if not executable:
        raise PlaytestLabError("Godot executable not found")
    source = source_head_sha if source_head_sha is not None else _git_sha(project_path)
    root = Path(output_root).resolve() / "playtest-lab" / f"{scenario['scenario_id']}-{persona}-{uuid4().hex[:12]}"
    root.mkdir(parents=True, exist_ok=False)
    (root / "scenario.json").write_bytes(scenario_source.read_bytes())
    _write(root / "session.json", {"schema_version": SCHEMA_VERSION, "scenario_id": scenario["scenario_id"],
          "persona": persona, "driver": driver, "evidence_class": EVIDENCE_LIVE, "source_head_sha": source})
    runner_script = Path(__file__).with_name("godot_playtest_runner.gd")
    if not runner_script.is_file():
        raise PlaytestLabError(f"Godot runner not found: {runner_script}")
    command = [executable, "--headless", "--path", str(project_path), "--script", str(runner_script)]
    env = os.environ.copy()
    env["MGSF_PLAYTEST_SCENARIO"] = str(root / "scenario.json")
    env["MGSF_PLAYTEST_TRACE"] = str(root / "trace.jsonl")
    try:
        result = subprocess.run(command, cwd=project_path, env=env, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr += "\nGodot playtest timeout"
    (root / "godot.stdout.txt").write_text(stdout, encoding="utf-8")
    (root / "godot.stderr.txt").write_text(stderr, encoding="utf-8")
    _write(root / "runner.json", {"schema_version": SCHEMA_VERSION, "runner": "godot-headless-script", "returncode": code,
        "command": command, "cwd": str(project_path), "scenario_sha256": _sha(root / "scenario.json"),
        "trace_sha256": _sha(root / "trace.jsonl") if (root / "trace.jsonl").is_file() else None,
        "stdout_sha256": _sha(root / "godot.stdout.txt"), "stderr_sha256": _sha(root / "godot.stderr.txt")})
    if not (root / "trace.jsonl").is_file():
        raise PlaytestLabError(f"Godot produced no trace; inspect {root / 'godot.stderr.txt'} (returncode={code})")
    return evaluate_session(root)


def write_refinement_brief(session_root: str | Path, output_root: str | Path) -> Path:
    result = evaluate_session(session_root)
    report = _json(result.report_path)
    if report["status"] == "HOLD":
        raise PlaytestLabError("fixture-only evidence cannot authorize a refinement plan")
    target = Path(output_root) / report["scenario_id"] / "REFINEMENT_PROMPT.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# MGSF AI Playtest Refinement Candidate\n\n"
        f"Scenario: `{report['scenario_id']}` | persona: `{report['persona']}`\n"
        f"Baseline trace SHA-256: `{report['trace_sha256']}`\n"
        f"Baseline source commit: `{report['source_head_sha']}`\n\n"
        f"Measured metrics: `{json.dumps(report['metrics'], sort_keys=True)}`\n\n"
        "Implement one small reversible improvement in the game project. Preserve the scenario and input plan.\n"
        "After edits, rerun `mgsf playtest-lab-godot` with the same scenario and persona, "
        "then `mgsf playtest-lab-compare` with the baseline and new session.\n"
        "Do not claim the game is fun based on these counters. Do not publish, merge, or ship.\n"
        "A reviewer must inspect code, the recording, and the comparison before accepting changes.\n",
        encoding="utf-8",
    )
    return target
