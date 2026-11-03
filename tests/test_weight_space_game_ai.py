from __future__ import annotations

import json
from pathlib import Path

import pytest

from mgsf.weight_space_game_ai import (
    ACTIONS,
    FEATURE_COUNT,
    Scenario,
    build_policy,
    load_fixture,
    observe,
    play,
    repair_hazard_weights,
    run_fixture,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/weight-space/gridworld-v1.json"


def test_direct_weights_are_explicit_sparse_affine_layer() -> None:
    policy = build_policy()
    assert len(policy.weights) == len(ACTIONS) == 5
    assert all(len(row) == FEATURE_COUNT == 25 for row in policy.weights)
    assert policy.weights[4][20] == 2.0  # right action: progress feature
    assert policy.weights[4][21] == 0.0  # right action: unsafe, prior to repair
    assert sum(v != 0 for row in policy.weights for v in row) == 20


def test_repair_changes_only_hazard_coefficients() -> None:
    before = build_policy()
    after, edits = repair_hazard_weights(before)
    assert len(edits) == 5
    actual = {(r, c) for r in range(5) for c in range(25) if before.weights[r][c] != after.weights[r][c]}
    assert actual == {(entry["row"], entry["column"]) for entry in edits}
    assert all(entry["before"] == 0 and entry["after"] == -30 for entry in edits)
    assert before.bias == after.bias
    assert before.weights[4][21] == 0  # original is immutable


def test_repaired_policy_avoids_hazard_and_reaches_goal() -> None:
    scenario = Scenario("hazard-in-line", 5, (0, 2), (4, 2), (2, 2), 18)
    original = build_policy()
    repaired, _ = repair_hazard_weights(original)
    assert play(scenario, original)["outcome"] == "hazard"
    completed = play(scenario, repaired)
    assert completed["outcome"] == "success"
    assert completed["steps"] == 6
    assert all(item["to"] != [2, 2] for item in completed["trace"])


def test_observation_penalizes_invalid_wall_move() -> None:
    scenario = Scenario("edge", 5, (0, 0), (4, 0), (2, 2), 18)
    observations = observe(scenario, scenario.start, {scenario.start})
    assert observations[2 * 5 + 2] == 0.0  # down is not a wall
    assert observations[1 * 5 + 2] == 1.0  # up is a wall
    assert observations[3 * 5 + 2] == 1.0  # left is a wall


def test_fixture_builds_reproducible_honestly_labeled_evidence(tmp_path: Path) -> None:
    first = run_fixture(FIXTURE, tmp_path / "first")
    second = run_fixture(FIXTURE, tmp_path / "second")
    assert first.read_bytes() == second.read_bytes()
    doc = json.loads(first.read_text(encoding="utf-8"))
    assert doc["evidence_class"] == "deterministic_weight_space_fixture"
    assert doc["promotion_gate"]["status"] == "HOLD"
    assert doc["real_game_measurement"] is False
    assert doc["trained"] is False
    assert doc["uses_gradients"] is False
    assert len(doc["weight_edits"]) == 5
    assert doc["policy_sha256"]["unrepaired"] != doc["policy_sha256"]["repaired"]
    baseline = doc["evaluations"]["unrepaired"]["summary"]
    repaired = doc["evaluations"]["repaired"]["summary"]
    assert baseline["successes"] == 4
    assert repaired["successes"] == 12
    assert repaired["hazard_failures"] == 0
    assert len(doc["evaluations"]["repaired"]["episodes"]) == 12


@pytest.mark.parametrize(
    "episode",
    [
        {"id": "x", "size": 5, "start": [0, 0], "goal": [0, 0], "hazard": [1, 1]},
        {"id": "x", "size": 5, "start": [0, 0], "goal": [2, 2], "hazard": [9, 1]},
        {"id": "x", "size": True, "start": [0, 0], "goal": [2, 2], "hazard": [1, 1]},
        {"id": "x", "size": 5, "start": [0, True], "goal": [2, 2], "hazard": [1, 1]},
        {"id": "x", "size": 5, "start": [0, 0], "goal": [2, 2], "hazard": [1, 1], "max_steps": 0},
    ],
)
def test_invalid_fixtures_are_rejected(tmp_path: Path, episode: dict) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"schema_version": 1, "episodes": [episode]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_fixture(path)


def test_duplicate_scenario_ids_rejected(tmp_path: Path) -> None:
    episode = {"id": "dup", "size": 5, "start": [0, 0], "goal": [2, 2], "hazard": [1, 1]}
    path = tmp_path / "dup.json"
    path.write_text(json.dumps({"schema_version": 1, "episodes": [episode, episode]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_fixture(path)


def test_non_negative_penalty_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        repair_hazard_weights(build_policy(), penalty=1)
