"""MGSF-WSP-M0.4: paired policy benchmark using SHADOW SUM's authored Godot rules.

The benchmark reads *clues* and requested post count only. The authored stage's
solution field is never included in planner input or sent to a policy. Godot's
original ShadowRules script is the authoritative evaluator. This is a rules-
kernel integration, not input automation of the shipped product's UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Sequence


GRID = 5
DEVELOPMENT_IDS = tuple(range(1, 7))
EVALUATION_IDS = tuple(range(7, 19))
# Five observed features, all derived from public clues, current posts and
# the candidate. Zero gradient fitting and no stage-solution lookups.
FEATURES = ("visible_l1_reduction", "new_exact_clues", "overshot_clues", "positive_clue_touches", "visible_clue_touches")
WEIGHTS = (2.0, 1.0, -4.0, 0.1, 0.0)
POLICIES = ("rule_greedy", "direct_weights")


@dataclass(frozen=True)
class Stage:
    id: int
    posts: int
    clues: tuple[tuple[int, ...], ...]


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def load_public_stages(source_path: str | Path) -> list[Stage]:
    """Parse authored stages but explicitly discard all hidden solution data."""
    raw = json.loads(Path(source_path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("stage pack must be a nonempty list")
    stages: list[Stage] = []
    ids: set[int] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("stage must be a mapping")
        sid, count, clues = entry.get("id"), entry.get("posts"), entry.get("clues")
        if type(sid) is not int or sid in ids or type(count) is not int or not 1 <= count <= 25:
            raise ValueError("invalid or duplicate stage id or post count")
        if not isinstance(clues, list) or len(clues) != GRID:
            raise ValueError("invalid clue dimensions")
        if any(not isinstance(row, list) or len(row) != GRID for row in clues):
            raise ValueError("invalid clue row dimensions")
        if any(type(n) is not int or n not in (-1, 0, 1, 2, 3) for row in clues for n in row):
            raise ValueError("invalid visible clue")
        stages.append(Stage(sid, count, tuple(tuple(row) for row in clues)))
        ids.add(sid)
    if tuple(sorted(ids)) != DEVELOPMENT_IDS + EVALUATION_IDS:
        raise ValueError("benchmark requires the pinned original eighteen-stage pack")
    return sorted(stages, key=lambda s: s.id)


def shadow(occupied: set[tuple[int, int]]) -> tuple[tuple[int, ...], ...]:
    """Planner's independently implemented shadow model; Godot verifies outcomes."""
    return tuple(
        tuple(
            int((r - 1, c) in occupied) +
            int((r, c - 1) in occupied) +
            int((r, c + 1) in occupied)
            for c in range(GRID)
        )
        for r in range(GRID)
    )


def visible_error(clues: Sequence[Sequence[int]], value: Sequence[Sequence[int]]) -> int:
    return sum(abs(target - value[r][c])
               for r, row in enumerate(clues) for c, target in enumerate(row) if target >= 0)


def _feature_vector(stage: Stage, occupied: set[tuple[int, int]], candidate: tuple[int, int]) -> tuple[float, ...]:
    before = shadow(occupied)
    after = shadow(occupied | {candidate})
    reduction = visible_error(stage.clues, before) - visible_error(stage.clues, after)
    new_exact = 0
    overshot = 0
    pos_touch = 0
    visible_touch = 0
    for r in range(GRID):
        for c in range(GRID):
            clue = stage.clues[r][c]
            if clue < 0:
                continue
            if after[r][c] != before[r][c]:
                visible_touch += 1
                pos_touch += int(clue > 0)
            if after[r][c] == clue and before[r][c] != clue:
                new_exact += 1
            if after[r][c] > clue:
                overshot += 1
    return (float(reduction), float(new_exact), float(overshot), float(pos_touch), float(visible_touch))


def choose_posts(stage: Stage, policy: str) -> dict[str, Any]:
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    selected: set[tuple[int, int]] = set()
    trace: list[dict[str, Any]] = []
    for turn in range(stage.posts):
        candidates = []
        for r in range(GRID):
            for c in range(GRID):
                if (r, c) in selected:
                    continue
                features = _feature_vector(stage, selected, (r, c))
                if policy == "rule_greedy":
                    # A transparent one-step rule: reduce visible error first,
                    # prefer exact matches second, avoid overshoots third.
                    score = (features[0], features[1], -features[2])
                else:
                    score = (sum(a * b for a, b in zip(WEIGHTS, features)),)
                candidates.append((score, (r, c), features))
        # Stable row-major tie break, no randomness and no access to solution.
        best = max(candidates, key=lambda item: item[0])
        location = best[1]
        selected.add(location)
        trace.append({
            "turn": turn + 1,
            "cell": list(location),
            "score": list(best[0]),
            "features": list(best[2]),
        })
    return {"policy": policy, "stage_id": stage.id, "placements": trace}


def build_plan(stages: list[Stage], source_stage_sha: str, source_rules_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "milestone": "MGSF-WSP-M0.4",
        "benchmark": "shadow-sum-authored-rules",
        "source_stage_sha256": source_stage_sha,
        "source_rules_sha256": source_rules_sha,
        "policies": list(POLICIES),
        "features": list(FEATURES),
        "direct_weights": list(WEIGHTS),
        "development_ids": list(DEVELOPMENT_IDS),
        "evaluation_ids": list(EVALUATION_IDS),
        "stage_inputs": [
            {
                "id": stage.id,
                "posts": stage.posts,
                "clues": [list(row) for row in stage.clues],
                "plans": {p: choose_posts(stage, p) for p in POLICIES},
            }
            for stage in stages
        ],
        "solution_fields_exported": False,
    }


def validate_game_trace(
    plan: dict[str, Any], result: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []
    if result.get("schema_version") != 1 or result.get("source_stage_sha256") != plan["source_stage_sha256"] or result.get("source_rules_sha256") != plan["source_rules_sha256"]:
        problems.append("engine trace has invalid schema or input source hashes")
    engine_stages = result.get("stages")
    if not isinstance(engine_stages, list) or len(engine_stages) != len(plan["stage_inputs"]):
        return problems + ["engine trace count differs"], {}
    summaries: dict[str, dict[str, Any]] = {
        split: {policy: {"stages": 0, "wins": 0, "total_visible_l1_error": 0, "results": []} for policy in POLICIES}
        for split in ("development", "evaluation")
    }
    for original, observed in zip(plan["stage_inputs"], engine_stages):
        if not isinstance(observed, dict) or observed.get("id") != original["id"]:
            problems.append("engine stage id mismatch")
            continue
        split = "development" if original["id"] in DEVELOPMENT_IDS else "evaluation"
        records = observed.get("policies")
        if not isinstance(records, dict) or set(records) != set(POLICIES):
            problems.append(f"stage {original['id']}: missing policies")
            continue
        for policy in POLICIES:
            value = records[policy]
            if not isinstance(value, dict):
                problems.append(f"stage {original['id']}/{policy}: invalid record")
                continue
            wanted_actions = [p["cell"] for p in original["plans"][policy]["placements"]]
            if value.get("placements") != wanted_actions:
                problems.append(f"stage {original['id']}/{policy}: actions differ from plan")
                continue
            expected_shadow = shadow({tuple(cell) for cell in wanted_actions})
            actual_shadow = value.get("shadow")
            if actual_shadow != [list(row) for row in expected_shadow]:
                problems.append(f"stage {original['id']}/{policy}: authored rules do not match planner shadow")
                continue
            expected_success = (len(wanted_actions) == original["posts"] and
                                all(original["clues"][r][c] < 0 or expected_shadow[r][c] == original["clues"][r][c]
                                    for r in range(GRID) for c in range(GRID)))
            expected_error = visible_error(original["clues"], expected_shadow)
            if type(value.get("success")) is not bool or value["success"] != expected_success:
                problems.append(f"stage {original['id']}/{policy}: engine win differs")
                continue
            if value.get("visible_l1_error") != expected_error:
                problems.append(f"stage {original['id']}/{policy}: engine error differs")
                continue
            if value.get("placed_count") != len(wanted_actions):
                problems.append(f"stage {original['id']}/{policy}: count mismatch")
                continue
            bucket = summaries[split][policy]
            bucket["stages"] += 1
            bucket["wins"] += int(expected_success)
            bucket["total_visible_l1_error"] += expected_error
            bucket["results"].append({
                "stage_id": original["id"], "success": expected_success,
                "visible_l1_error": expected_error,
                "actions": wanted_actions,
            })
    for split in summaries:
        for policy in POLICIES:
            record = summaries[split][policy]
            if record["stages"] != len(DEVELOPMENT_IDS if split == "development" else EVALUATION_IDS):
                problems.append(f"{split}/{policy}: incomplete paired set")
            record["win_rate"] = round(record["wins"] / record["stages"], 6) if record["stages"] else None
    return problems, summaries


def _exec(command: list[str], log: Path, *, timeout: int, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, env=env)
        log.write_text(f"returncode={result.returncode}\ncommand={' '.join(command)}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n", encoding="utf-8")
        return result
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.write_text(f"command={' '.join(command)}\nerror={type(exc).__name__}: {exc}\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 124, "", str(exc))


def _source_head(repo: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def run_shadow_sum_benchmark(
    project: str | Path,
    godot_executable: str,
    output_root: str | Path,
    runner_script: str | Path,
) -> Path:
    """Use a temporary Godot project that loads SHADOW SUM's unchanged rules/stages."""
    source = Path(project).resolve()
    rules = source / "src/shadow_rules.gd"
    stages_path = source / "data/stages_v0_1.json"
    runner = Path(runner_script).resolve()
    if not all(x.is_file() for x in (rules, stages_path, runner, source / "project.godot")):
        raise ValueError("source SHADOW SUM checkout or Godot runner is incomplete")
    godot = shutil.which(godot_executable)
    if godot is None and Path(godot_executable).is_file():
        godot = str(Path(godot_executable).resolve())
    if not godot:
        raise ValueError("Godot executable not found")
    root = Path(output_root).resolve() / "shadow-sum-neural-benchmark"
    root.mkdir(parents=True, exist_ok=True)
    result_file = root / "godot-results.json"
    result_file.unlink(missing_ok=True)
    public_stages = load_public_stages(stages_path)
    input_plan = build_plan(public_stages, _sha(stages_path), _sha(rules))
    plan_file = root / "policy-plans.json"
    _json(plan_file, input_plan)
    # The runner does NOT mutate or execute the existing game UI; it calls the
    # original ShadowRules and stage pack in a disposable Godot project.
    with tempfile.TemporaryDirectory(prefix="mgsf-shadow-sum-") as workspace:
        mirror = Path(workspace)
        (mirror / "src").mkdir()
        (mirror / "data").mkdir()
        (mirror / "bench").mkdir()
        shutil.copy2(rules, mirror / "src/shadow_rules.gd")
        shutil.copy2(stages_path, mirror / "data/stages_v0_1.json")
        shutil.copy2(runner, mirror / "bench/run.gd")
        (mirror / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="MGSF Shadow Sum Rules Benchmark"\n', encoding="utf-8"
        )
        env = os.environ.copy()
        env["MGSF_SHADOW_PLAN"] = str(plan_file)
        env["MGSF_SHADOW_RESULT"] = str(result_file)
        command = [godot, "--headless", "--path", str(mirror), "--script", "res://bench/run.gd"]
        proc = _exec(command, root / "godot-runtime.log", timeout=90, env=env)
    errors = []
    output = None
    if proc.returncode != 0 or "MGSF_SHADOW_BENCHMARK_OK" not in proc.stdout:
        errors.append("actual Godot benchmark execution failed")
    if not result_file.is_file():
        errors.append("Godot did not create a result JSON")
    else:
        try:
            output = json.loads(result_file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            errors.append("invalid Godot result JSON")
    if isinstance(output, dict):
        details, summaries = validate_game_trace(input_plan, output)
        errors.extend(details)
    else:
        summaries = {}
    artifacts = {}
    for name in ("policy-plans.json", "godot-results.json", "godot-runtime.log"):
        path = root / name
        if path.is_file():
            artifacts[name] = {"sha256": _sha(path), "bytes": path.stat().st_size}
    report = {
        "schema_version": 1,
        "service": "neural-game-intelligence-benchmark",
        "milestone": "MGSF-WSP-M0.4",
        "evidence_class": "recorded_authored_godot_rules_benchmark",
        "source_repo": "madowaku/shadow-sum",
        "source_head_sha": _source_head(source),
        "source_sha256": {
            "shadow_rules.gd": _sha(rules), "stages_v0_1.json": _sha(stages_path),
            "godot_benchmark_runner.gd": _sha(runner),
        },
        "engine_kernel": "original ShadowRules in isolated Godot runtime",
        "full_game_ui_executed": False,
        "stage_solutions_used_by_policies": False,
        "weights_hand_authored_without_training": True,
        "common_action_budget": "exact required post count per authored stage",
        "fixed_splits": {"development": list(DEVELOPMENT_IDS), "evaluation": list(EVALUATION_IDS)},
        "comparators": {
            "rule_greedy": "visible L1 improvement, then exact matches, then avoid overshoots",
            "direct_weights": {"features": FEATURES, "weights": WEIGHTS, "architecture": "hand_written_linear_candidate_scorer"},
        },
        "summaries": summaries,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "artifacts": artifacts,
        "promotion_gate": {
            "status": "HOLD",
            "reason": "authored game's true rules/stages verified in Godot, but the full UI "
                      "was not operated and both policies are hand-designed on a known published stage pack",
        },
    }
    evidence = root / "shadow-sum-neural-benchmark-evidence.json"
    _json(evidence, report)
    return evidence
