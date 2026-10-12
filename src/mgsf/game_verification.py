"""Fail-closed, fixture-only game specification/replay verifier (MGSF-M0.9).

This module checks trace data against declared requirements. It does NOT run Godot
or certify that a trace came from a real engine. A passing fixture always HOLDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from typing import Any

import yaml

EVIDENCE_CLASS = "deterministic_game_fixture"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_STATE_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_MISSING = object()


class GameVerificationError(ValueError):
    """Invalid game verification contract or unsafe input."""


@dataclass(frozen=True)
class GameVerificationResult:
    root: Path
    status: str
    verification_status: str
    requirement_count: int
    covered_count: int
    failed_requirements: tuple[str, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GameVerificationError(message)


def _identifier(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(_ID.fullmatch(value))
             and ".." not in value, f"{label} must be a safe ASCII identifier")
    return value


def _assertion(assertion: Any, requirement_id: str, expected_steps: int) -> None:
    _require(isinstance(assertion, dict), f"{requirement_id}: assertion must be a mapping")
    if "event" in assertion:
        _require(set(assertion) == {"event", "count"},
                 f"{requirement_id}: event assertion must have event and count only")
        _require(isinstance(assertion["event"], str) and bool(assertion["event"]),
                 f"{requirement_id}: event must be nonempty")
        _require(type(assertion["count"]) is int and assertion["count"] >= 0,
                 f"{requirement_id}: count must be a nonnegative integer")
    else:
        _require("path" in assertion and _STATE_PATH.fullmatch(str(assertion["path"])) is not None,
                 f"{requirement_id}: invalid state path")
        has_equal = "equals" in assertion
        has_same = "same_as_before" in assertion
        _require(has_equal != has_same, f"{requirement_id}: choose equals OR same_as_before")
        _require(set(assertion) <= {"path", "equals", "same_as_before", "at_step"},
                 f"{requirement_id}: unsupported assertion key")
        if has_same:
            _require(assertion["same_as_before"] is True,
                     f"{requirement_id}: same_as_before must be true")
        idx = assertion.get("at_step", expected_steps - 1)
        _require(type(idx) is int and 0 <= idx < expected_steps,
                 f"{requirement_id}: at_step out of replay range")


def load_game_spec(path: str | Path) -> dict[str, Any]:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(spec, dict) and spec.get("schema_version") == 1,
             "game spec schema_version must be 1")
    _identifier(spec.get("game_id"), "game_id")
    requirements = spec.get("requirements")
    _require(isinstance(requirements, list) and bool(requirements),
             "spec requires a nonempty requirements list")
    seen: set[str] = set()
    for requirement in requirements:
        _require(isinstance(requirement, dict), "each requirement must be a mapping")
        rid = _identifier(requirement.get("id"), "requirement id")
        _require(rid not in seen, f"duplicate requirement: {rid}")
        seen.add(rid)
        _require(type(requirement.get("critical")) is bool,
                 f"{rid}: critical must be a boolean")
        _require(isinstance(requirement.get("description"), str)
                 and bool(requirement["description"].strip()),
                 f"{rid}: description must be nonempty")
        actions = requirement.get("actions")
        _require(isinstance(actions, list) and bool(actions),
                 f"{rid}: actions must be a nonempty list")
        expected_steps = 0
        for action in actions:
            _require(isinstance(action, dict) and set(action) <= {"action", "repeat"}
                     and isinstance(action.get("action"), str) and bool(action["action"]),
                     f"{rid}: invalid replay action")
            repeat = action.get("repeat", 1)
            _require(type(repeat) is int and 1 <= repeat <= 100,
                     f"{rid}: repeat must be 1..100")
            expected_steps += repeat
        _require(expected_steps <= 500, f"{rid}: replay too long")
        assertions = requirement.get("assertions")
        _require(isinstance(assertions, list) and bool(assertions),
                 f"{rid}: assertions must be a nonempty list")
        for assertion in assertions:
            _assertion(assertion, rid, expected_steps)
    return spec


def load_game_trace(path: str | Path, game_id: str) -> dict[str, Any]:
    trace = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(trace, dict) and trace.get("schema_version") == 1,
             "trace schema_version must be 1")
    _require(trace.get("game_id") == game_id, "trace game_id does not match spec")
    _require(trace.get("evidence_class") == EVIDENCE_CLASS,
             "v0.1 accepts only deterministic_game_fixture; live evidence needs a trusted runner")
    cases = trace.get("cases")
    _require(isinstance(cases, list), "trace cases must be a list")
    seen: set[str] = set()
    for case in cases:
        _require(isinstance(case, dict), "case must be a mapping")
        rid = _identifier(case.get("requirement_id"), "case requirement_id")
        _require(rid not in seen, f"duplicate trace case: {rid}")
        seen.add(rid)
        steps = case.get("steps")
        _require(isinstance(steps, list) and len(steps) <= 500, f"{rid}: invalid steps")
        for step in steps:
            _require(isinstance(step, dict)
                     and isinstance(step.get("action"), str)
                     and isinstance(step.get("state_before"), dict)
                     and isinstance(step.get("state_after"), dict)
                     and isinstance(step.get("events"), list)
                     and all(isinstance(event, str) for event in step["events"]),
                     f"{rid}: step missing action/state_before/state_after/events")
    return trace


def _at(state: dict[str, Any], path: str) -> Any:
    value: Any = state
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _expected_actions(requirement: dict[str, Any]) -> list[str]:
    return [action["action"] for item in requirement["actions"]
            for action in [item] * item.get("repeat", 1)]


def _evaluate_case(requirement: dict[str, Any], case: dict[str, Any] | None) -> dict[str, Any]:
    rid = requirement["id"]
    if case is None:
        return {"id": rid, "critical": requirement["critical"], "status": "FAIL",
                "covered": False, "checks": [
                    {"check": "replay_present", "passed": False,
                     "reason": "missing requirement replay (implementation omission not ruled out)"}
                ]}
    steps = case["steps"]
    expected = _expected_actions(requirement)
    observed = [step["action"] for step in steps]
    checks: list[dict[str, Any]] = [{
        "check": "replay_actions",
        "passed": expected == observed,
        "reason": "actions match declared replay" if expected == observed
                  else f"action mismatch: expected {expected!r}, observed {observed!r}",
    }]
    # Mismatched replay must never be interpreted as passing state evidence.
    if expected != observed:
        return {"id": rid, "critical": requirement["critical"], "covered": True,
                "status": "FAIL", "checks": checks}

    for i, assertion in enumerate(requirement["assertions"]):
        if "event" in assertion:
            observed_count = sum(step["events"].count(assertion["event"]) for step in steps)
            passed = observed_count == assertion["count"]
            reason = f"event {assertion['event']}: expected {assertion['count']}, observed {observed_count}"
        else:
            index = assertion.get("at_step", len(steps) - 1)
            step = steps[index]
            actual = _at(step["state_after"], assertion["path"])
            target = (_at(step["state_before"], assertion["path"])
                      if "same_as_before" in assertion else assertion["equals"])
            passed = actual is not _MISSING and target is not _MISSING and actual == target
            reason = (f"step {index} {assertion['path']}: "
                      f"expected {target if target is not _MISSING else '<missing>'!r}, "
                      f"observed {actual if actual is not _MISSING else '<missing>'!r}")
        checks.append({"check": f"assertion_{i + 1}", "passed": passed, "reason": reason})
    return {"id": rid, "critical": requirement["critical"], "covered": True,
            "status": "PASS" if all(c["passed"] for c in checks) else "FAIL",
            "checks": checks}


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def run_game_verification(
    spec_path: str | Path,
    trace_path: str | Path,
    output_root: str | Path = "evidence/ai-game-verification",
) -> GameVerificationResult:
    spec_file, trace_file = Path(spec_path), Path(trace_path)
    spec = load_game_spec(spec_file)
    trace = load_game_trace(trace_file, spec["game_id"])
    requirement_ids = {req["id"] for req in spec["requirements"]}
    unknown = {case["requirement_id"] for case in trace["cases"]} - requirement_ids
    _require(not unknown, f"undeclared trace cases: {sorted(unknown)}")
    by_id = {case["requirement_id"]: case for case in trace["cases"]}
    evaluated = [_evaluate_case(req, by_id.get(req["id"])) for req in spec["requirements"]]
    failed = tuple(req["id"] for req in evaluated if req["status"] != "PASS")
    covered = sum(req["covered"] for req in evaluated)
    verification_status = "FAIL" if failed else "PASS"
    status = "FAIL" if failed else "HOLD"
    root = Path(output_root) / spec["game_id"]
    root.mkdir(parents=True, exist_ok=True)
    # Preserve the exact inputs and hashes, rather than trusting a model's summary.
    spec_copy = root / "spec.yaml"
    trace_copy = root / "trace.json"
    if spec_file.resolve() != spec_copy.resolve():
        shutil.copyfile(spec_file, spec_copy)
    if trace_file.resolve() != trace_copy.resolve():
        shutil.copyfile(trace_file, trace_copy)
    report = {
        "schema_version": 1,
        "service": "ai-game-verification",
        "game_id": spec["game_id"],
        "evidence_class": EVIDENCE_CLASS,
        "verification_status": verification_status,
        "status": status,
        "release_gate": status,
        "reason": ("fixture verification failed" if failed else
                   "fixture checks pass, but no trusted engine-runner or human playtest evidence"),
        "requirement_count": len(evaluated),
        "covered_count": covered,
        "coverage_ratio": covered / len(evaluated),
        "failed_requirements": list(failed),
        "results": evaluated,
        "source": {
            "spec": {"path": "spec.yaml", "sha256": _digest(spec_copy)},
            "trace": {"path": "trace.json", "sha256": _digest(trace_copy)},
        },
        "human_playtest_verified": False,
        "trusted_engine_execution_verified": False,
    }
    (root / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return GameVerificationResult(
        root=root, status=status, verification_status=verification_status,
        requirement_count=len(evaluated), covered_count=covered,
        failed_requirements=failed,
    )
