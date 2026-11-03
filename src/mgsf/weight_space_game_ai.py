"""Deterministic, no-training weight-space policy experiment for a tiny grid game.

This is an independently authored engineering demonstration inspired by the
Weight-Space Programming research, not a reproduction of its reported results.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import random
from typing import Any

ACTIONS: tuple[tuple[str, tuple[int, int]], ...] = (
    ("noop", (0, 0)),
    ("up", (0, -1)),
    ("down", (0, 1)),
    ("left", (-1, 0)),
    ("right", (1, 0)),
)
FEATURES = ("goal_progress", "hazard", "wall", "visited", "noop")
FEATURE_COUNT = len(ACTIONS) * len(FEATURES)


@dataclass(frozen=True)
class Scenario:
    id: str
    size: int
    start: tuple[int, int]
    goal: tuple[int, int]
    hazard: tuple[int, int]
    max_steps: int


@dataclass(frozen=True)
class LinearPolicy:
    """5-action affine neural layer: logits = W @ features + b."""

    weights: tuple[tuple[float, ...], ...]
    bias: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.weights) != len(ACTIONS) or len(self.bias) != len(ACTIONS):
            raise ValueError("expected five action rows and biases")
        if any(len(row) != FEATURE_COUNT for row in self.weights):
            raise ValueError("expected 25 input weights per action")

    def logits(self, observation: tuple[float, ...]) -> tuple[float, ...]:
        if len(observation) != FEATURE_COUNT:
            raise ValueError("invalid observation length")
        return tuple(
            sum(weight * value for weight, value in zip(row, observation)) + bias
            for row, bias in zip(self.weights, self.bias)
        )

    def as_dict(self) -> dict[str, Any]:
        return {"architecture": "linear_25_to_5", "weights": self.weights, "bias": self.bias}


def build_policy(*, hazard_penalty: float = 0.0) -> LinearPolicy:
    """Write an explicit sparse weight matrix without a training algorithm."""
    weights = [[0.0] * FEATURE_COUNT for _ in ACTIONS]
    for action_idx in range(len(ACTIONS)):
        feature_offset = action_idx * len(FEATURES)
        for feature_idx, coefficient in enumerate((2.0, hazard_penalty, -100.0, -4.0, -4.0)):
            weights[action_idx][feature_offset + feature_idx] = coefficient
    return LinearPolicy(tuple(tuple(row) for row in weights), (0.0,) * len(ACTIONS))


def repair_hazard_weights(policy: LinearPolicy, *, penalty: float = -30.0) -> tuple[LinearPolicy, list[dict[str, Any]]]:
    """Directly edit exactly five hazard coefficients, with no gradients or fitting."""
    if penalty >= 0:
        raise ValueError("hazard penalty must be negative")
    weights = [list(row) for row in policy.weights]
    edits: list[dict[str, Any]] = []
    for action_idx, (name, _) in enumerate(ACTIONS):
        column = action_idx * len(FEATURES) + FEATURES.index("hazard")
        before = weights[action_idx][column]
        weights[action_idx][column] = penalty
        edits.append({"action": name, "row": action_idx, "column": column, "before": before, "after": penalty})
    return LinearPolicy(tuple(tuple(row) for row in weights), policy.bias), edits


def _distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def observe(scenario: Scenario, position: tuple[int, int], visited: set[tuple[int, int]]) -> tuple[float, ...]:
    """Action-local features, not a path finder or a hardcoded game solver."""
    values: list[float] = []
    for name, (dx, dy) in ACTIONS:
        candidate = (position[0] + dx, position[1] + dy)
        wall = not (0 <= candidate[0] < scenario.size and 0 <= candidate[1] < scenario.size)
        if wall:
            candidate = position
        values.extend((
            float(_distance(position, scenario.goal) - _distance(candidate, scenario.goal)),
            float(candidate == scenario.hazard),
            float(wall),
            float(candidate in visited),
            float(name == "noop"),
        ))
    return tuple(values)


def _validate_coordinate(value: Any, *, size: int, field: str) -> tuple[int, int]:
    if not (isinstance(value, list) and len(value) == 2 and all(type(v) is int for v in value)):
        raise ValueError(f"{field} must be a pair of integers")
    x, y = value
    if not (0 <= x < size and 0 <= y < size):
        raise ValueError(f"{field} outside board")
    return x, y


def load_fixture(path: str | Path) -> list[Scenario]:
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(source, dict) or source.get("schema_version") != 1:
        raise ValueError("fixture schema_version must be 1")
    episodes = source.get("episodes")
    if not isinstance(episodes, list) or not 1 <= len(episodes) <= 200:
        raise ValueError("episodes must have 1 to 200 entries")
    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for raw in episodes:
        if not isinstance(raw, dict):
            raise ValueError("each episode must be an object")
        name = raw.get("id")
        size = raw.get("size")
        steps = raw.get("max_steps", 20)
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("episode ids must be unique nonempty strings")
        if type(size) is not int or not 3 <= size <= 12:
            raise ValueError("size must be between 3 and 12")
        if type(steps) is not int or not 1 <= steps <= 200:
            raise ValueError("max_steps must be between 1 and 200")
        start = _validate_coordinate(raw.get("start"), size=size, field="start")
        goal = _validate_coordinate(raw.get("goal"), size=size, field="goal")
        hazard = _validate_coordinate(raw.get("hazard"), size=size, field="hazard")
        if len({start, goal, hazard}) != 3:
            raise ValueError("start, goal, and hazard must be different")
        scenarios.append(Scenario(name, size, start, goal, hazard, steps))
        seen.add(name)
    return scenarios


def play(scenario: Scenario, policy: LinearPolicy | None, *, random_seed: int = 0) -> dict[str, Any]:
    """Run a fixed-horizon episode; policy=None is a seeded random baseline."""
    position = scenario.start
    visited = {position}
    rng = random.Random(random_seed)
    trace: list[dict[str, Any]] = []
    outcome = "timeout"
    for step in range(1, scenario.max_steps + 1):
        if policy is None:
            action_idx = rng.randrange(len(ACTIONS))
        else:
            scores = policy.logits(observe(scenario, position, visited))
            action_idx = max(range(len(scores)), key=lambda index: scores[index])
        action, (dx, dy) = ACTIONS[action_idx]
        candidate = (position[0] + dx, position[1] + dy)
        wall = not (0 <= candidate[0] < scenario.size and 0 <= candidate[1] < scenario.size)
        if wall:
            candidate = position
        trace.append({"step": step, "action": action, "from": list(position), "to": list(candidate), "wall": wall})
        position = candidate
        visited.add(position)
        if position == scenario.hazard:
            outcome = "hazard"
            break
        if position == scenario.goal:
            outcome = "success"
            break
    return {"scenario_id": scenario.id, "outcome": outcome, "steps": len(trace), "trace": trace}


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    successful = [r for r in results if r["outcome"] == "success"]
    return {
        "episodes": n,
        "successes": len(successful),
        "hazard_failures": sum(r["outcome"] == "hazard" for r in results),
        "timeouts": sum(r["outcome"] == "timeout" for r in results),
        "success_rate": round(len(successful) / n, 6),
        "mean_steps_on_success": round(sum(r["steps"] for r in successful) / len(successful), 3) if successful else None,
    }


def _hash_object(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def run_fixture(fixture: str | Path, output_root: str | Path) -> Path:
    """Write inspectable deterministic evidence. Fixture evidence never promotes."""
    scenarios = load_fixture(fixture)
    baseline = build_policy()
    repaired, edits = repair_hazard_weights(baseline)
    edited_coordinates = {(edit["row"], edit["column"]) for edit in edits}
    if any(
        baseline.weights[row][col] != repaired.weights[row][col]
        for row in range(len(ACTIONS))
        for col in range(FEATURE_COUNT)
        if (row, col) not in edited_coordinates
    ):
        raise AssertionError("repair must affect only specified coefficients")
    policies = {"random": None, "unrepaired": baseline, "repaired": repaired}
    evaluations: dict[str, Any] = {}
    for name, policy in policies.items():
        results = [
            play(scenario, policy, random_seed=int.from_bytes(sha256(f"{scenario.id}:2026".encode()).digest()[:8], "big"))
            for scenario in scenarios
        ]
        evaluations[name] = {"summary": _summary(results), "episodes": results}
    document = {
        "schema_version": 1,
        "service": "weight-space-game-ai-lab",
        "milestone": "MGSF-WSP-M0.1",
        "evidence_class": "deterministic_weight_space_fixture",
        "real_game_measurement": False,
        "trained": False,
        "uses_gradients": False,
        "source_fixture": str(Path(fixture)),
        "source_fixture_sha256": sha256(Path(fixture).read_bytes()).hexdigest(),
        "observation_features": FEATURES,
        "action_order": [name for name, _ in ACTIONS],
        "architecture": "linear_25_to_5",
        "policy_sha256": {"unrepaired": _hash_object(baseline.as_dict()), "repaired": _hash_object(repaired.as_dict())},
        "policies": {"unrepaired": baseline.as_dict(), "repaired": repaired.as_dict()},
        "weight_edits": edits,
        "evaluations": evaluations,
        "promotion_gate": {"status": "HOLD", "reason": "deterministic fixture only; real game adapter and independent evaluation required"},
        "research_context": "Inspired by Takehi et al., Sparks of Weight-Space Programming (2026); not a reproduction.",
    }
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "weight-space-game-ai-evidence.json"
    dest.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest
