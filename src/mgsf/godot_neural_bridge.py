"""Run the M0.2 policy inside a real, small Godot game and validate evidence.

Godot owns game runtime, rendering and trace creation. Python independently
checks the trace against M0.2's exact expected action sequence. The target
remains a self-contained Godot FIXTURE, not an external authored game.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .neural_behavior_intelligence import inspect_episode
from .weight_space_game_ai import ACTIONS, FEATURES, LinearPolicy, Scenario


@dataclass(frozen=True)
class GodotNeuralBridgeRun:
    evidence_path: Path
    status: str
    matched_episodes: int
    images: tuple[Path, ...]


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _coordinate(raw: Any, size: int, name: str) -> tuple[int, int]:
    if not isinstance(raw, list) or len(raw) != 2 or any(type(v) is not int for v in raw):
        raise ValueError(f"{name} must be a list of two integers")
    if any(not (0 <= v < size) for v in raw):
        raise ValueError(f"{name} outside {size}x{size} board")
    return tuple(raw)  # type: ignore[return-value]


def load_handoff(path: str | Path) -> tuple[dict[str, Any], LinearPolicy, list[Scenario]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("handoff schema version must be 1")
    if payload.get("contract_kind") != "godot_gridworld_handoff":
        raise ValueError("unsupported Godot bridge contract")
    if payload.get("execution_status") != "not_executed":
        raise ValueError("handoff must be an unexecuted M0.2 contract")
    if payload.get("feature_order") != list(FEATURES):
        raise ValueError("feature order mismatch")
    if payload.get("action_deltas") != {name: list(delta) for name, delta in ACTIONS}:
        raise ValueError("action order or coordinate convention mismatch")
    policy_data = payload.get("policy")
    if not isinstance(policy_data, dict) or policy_data.get("architecture") != "linear_25_to_5":
        raise ValueError("unsupported policy architecture")
    rows, biases = policy_data.get("weights"), policy_data.get("bias")
    if not isinstance(rows, (tuple, list)) or not isinstance(biases, (tuple, list)):
        raise ValueError("policy weights and biases must be arrays")
    if any(type(value) not in (int, float) or not math.isfinite(value) for row in rows for value in row):
        raise ValueError("weights must be finite numbers")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in biases):
        raise ValueError("biases must be finite numbers")
    policy = LinearPolicy(
        tuple(tuple(float(x) for x in row) for row in rows),
        tuple(float(x) for x in biases),
    )
    raw_episodes = payload.get("episodes")
    if not isinstance(raw_episodes, list) or not 1 <= len(raw_episodes) <= 200:
        raise ValueError("handoff episodes must contain 1..200 cases")
    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for entry in raw_episodes:
        if not isinstance(entry, dict):
            raise ValueError("episode must be an object")
        sid, size, horizon = entry.get("id"), entry.get("size"), entry.get("max_steps")
        if not isinstance(sid, str) or not sid or sid in seen:
            raise ValueError("episode id must be unique and nonempty")
        if type(size) is not int or not 3 <= size <= 12:
            raise ValueError("invalid board size")
        if type(horizon) is not int or not 1 <= horizon <= 200:
            raise ValueError("invalid episode horizon")
        start = _coordinate(entry.get("start"), size, "start")
        goal = _coordinate(entry.get("goal"), size, "goal")
        hazard = _coordinate(entry.get("hazard"), size, "hazard")
        if len({start, goal, hazard}) != 3:
            raise ValueError("start, goal, hazard must be distinct")
        scenarios.append(Scenario(sid, size, start, goal, hazard, horizon))
        seen.add(sid)
    return payload, policy, scenarios


def _compare_trace(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    sid = expected["scenario_id"]
    for key in ("scenario_id", "outcome", "steps"):
        if actual.get(key) != expected[key]:
            problems.append(f"{sid}: {key} differs")
    observed = actual.get("trace")
    original = expected["trace"]
    if not isinstance(observed, list) or len(observed) != len(original):
        problems.append(f"{sid}: trace length differs")
        return problems
    for step, (want, got) in enumerate(zip(original, observed), start=1):
        for field in ("step", "from", "to", "wall"):
            if got.get(field) != want[field]:
                problems.append(f"{sid} step {step}: {field} differs")
        decision = got.get("decision")
        if not isinstance(decision, dict):
            problems.append(f"{sid} step {step}: decision absent")
            continue
        for field in ("winner", "winner_index"):
            if decision.get(field) != want["decision"][field]:
                problems.append(f"{sid} step {step}: {field} differs")
        logits = decision.get("logits")
        if not isinstance(logits, list) or len(logits) != len(ACTIONS):
            problems.append(f"{sid} step {step}: logits missing")
            continue
        for action, (wanted_action, got_value) in enumerate(zip(want["decision"]["actions"], logits)):
            if type(got_value) not in (int, float) or not math.isfinite(got_value) or abs(got_value - wanted_action["logit"]) > 1e-6:
                problems.append(f"{sid} step {step}: logit {action} differs")
    return problems


def _png_is_real_frame(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 1000:
        return False
    with path.open("rb") as file:
        header = file.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return False
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width == 640 and height == 640


def _git_head(project: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def _command(command: list[str], *, env: dict[str, str], log: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command, env=env, text=True, capture_output=True, timeout=timeout,
            check=False,
        )
        log.write_text(
            "command=" + " ".join(command) + "\nreturncode=" + str(completed.returncode)
            + "\n--- stdout ---\n" + completed.stdout + "\n--- stderr ---\n" + completed.stderr + "\n",
            encoding="utf-8",
        )
        return completed
    except subprocess.TimeoutExpired as exc:
        log.write_text("command=" + " ".join(command) + "\nreturncode=TIMEOUT\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 124, "", f"timeout after {timeout}s: {exc}")
    except OSError as exc:
        log.write_text("command=" + " ".join(command) + "\nlaunch_error=" + str(exc) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 127, "", str(exc))


def run_godot_neural_bridge(
    handoff_path: str | Path,
    project_path: str | Path,
    godot_executable: str,
    output_root: str | Path,
    *,
    count: int = 6,
    xvfb: bool = False,
) -> GodotNeuralBridgeRun:
    handoff = Path(handoff_path).resolve()
    project = Path(project_path).resolve()
    _, policy, scenarios = load_handoff(handoff)
    if not 1 <= count <= len(scenarios):
        raise ValueError("requested episode count outside handoff range")
    required = ("project.godot", "bridge.tscn", "bridge.gd")
    if any(not (project / path).is_file() for path in required):
        raise ValueError("Godot bridge project is missing its required files")
    godot = shutil.which(godot_executable)
    if godot is None and Path(godot_executable).is_file():
        godot = str(Path(godot_executable).resolve())
    if godot is None:
        raise ValueError("Godot executable not found")
    if xvfb and not shutil.which("xvfb-run"):
        raise ValueError("xvfb-run executable not found")

    root = Path(output_root).resolve() / "godot-neural-bridge"
    root.mkdir(parents=True, exist_ok=True)
    trace_path = root / "godot-trace.json"
    before = root / "before.png"
    after = root / "after.png"
    for stale in (trace_path, before, after):
        stale.unlink(missing_ok=True)
    env = os.environ.copy()
    env.update({
        "MGSF_BRIDGE_HANDOFF": str(handoff),
        "MGSF_BRIDGE_OUTPUT": str(root),
        "MGSF_BRIDGE_CASES": str(count),
    })
    # Preserve the source hashes before execution to tie the runtime evidence
    # to the exact project and handoff the runner inspected.
    source_hashes = {name: _digest(project / name) for name in required}
    source_hashes["handoff.json"] = _digest(handoff)
    expected = [inspect_episode(s, policy) for s in scenarios[:count]]

    version = _command([godot, "--version"], env=env, log=root / "godot-version.log", timeout=15)
    preflight = _command(
        [godot, "--headless", "--editor", "--path", str(project), "--quit-after", "1"],
        env=env, log=root / "godot-preflight.log", timeout=60,
    )
    runtime = subprocess.CompletedProcess(["not-run"], 1, "", "preflight not successful")
    if preflight.returncode == 0 and version.returncode == 0:
        command = ([ "xvfb-run", "-a" ] if xvfb else []) + [
            godot, "--path", str(project), "--scene", "res://bridge.tscn",
        ]
        runtime = _command(command, env=env, log=root / "godot-runtime.log", timeout=120)
    else:
        (root / "godot-runtime.log").write_text("skipped: version/preflight failed\n", encoding="utf-8")

    errors: list[str] = []
    match_count = 0
    image_paths: tuple[Path, ...] = ()
    try:
        if preflight.returncode != 0:
            errors.append("Godot project preflight failed")
        if version.returncode != 0:
            errors.append("Godot version command failed")
        if runtime.returncode != 0 or "MGSF_NEURAL_BRIDGE_OK" not in runtime.stdout:
            errors.append("Godot runtime did not complete with a verified exit and marker")
        if not trace_path.is_file():
            errors.append("Godot runtime trace missing")
        else:
            godot_record = json.loads(trace_path.read_text(encoding="utf-8"))
            if godot_record.get("engine") != "Godot" or godot_record.get("execution_status") != "completed":
                errors.append("Godot trace metadata invalid")
            if godot_record.get("source_handoff_sha256") != source_hashes["handoff.json"]:
                errors.append("Godot did not attest to the exact handoff hash")
            episodes = godot_record.get("episodes")
            if not isinstance(episodes, list) or len(episodes) != count:
                errors.append("Godot trace episode count mismatch")
            else:
                for oracle, recorded in zip(expected, episodes):
                    if not isinstance(recorded, dict):
                        errors.append("Godot recorded episode not a dictionary")
                        continue
                    differences = _compare_trace(oracle, recorded)
                    if differences:
                        errors.extend(differences[:8])
                    else:
                        match_count += 1
        if not _png_is_real_frame(before) or not _png_is_real_frame(after):
            errors.append("Godot viewport frames missing or invalid")
        elif _digest(before) == _digest(after):
            errors.append("Godot viewport frames identical across game progression")
        else:
            image_paths = (before, after)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"invalid Godot evidence: {type(exc).__name__}: {exc}")

    artifacts = {
        path.name: {"sha256": _digest(path), "bytes": path.stat().st_size}
        for path in (root / "godot-version.log", root / "godot-preflight.log",
                     root / "godot-runtime.log", trace_path, before, after)
        if path.is_file()
    }
    success = not errors and match_count == count
    document = {
        "schema_version": 1,
        "milestone": "MGSF-WSP-M0.3",
        "service": "neural-game-agent-bridge",
        "evidence_class": "recorded_godot_neural_fixture_run",
        "engine_executed": preflight.returncode == 0 and runtime.returncode == 0,
        "game_target": "self_contained_godot_neural_grid_fixture",
        "production_game_measurement": False,
        "source_head_sha": _git_head(project),
        "source_sha256": source_hashes,
        "godot_version": version.stdout.strip() if version.returncode == 0 else None,
        "requested_episodes": count,
        "matched_episodes": match_count,
        "float_score_tolerance": 1e-6,
        "screenshots_are_direct_godot_viewport_capture": len(image_paths) == 2 and runtime.returncode == 0,
        "artifacts": artifacts,
        "errors": errors,
        "status": "PASS" if success else "FAIL",
        "promotion_gate": {
            "status": "HOLD",
            "reason": "Godot integration validated in a standalone test game only; "
                      "actual authored-game integration and independent evaluation remain",
        },
    }
    evidence_path = root / "godot-neural-bridge-evidence.json"
    evidence_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return GodotNeuralBridgeRun(evidence_path, document["status"], match_count, image_paths)
