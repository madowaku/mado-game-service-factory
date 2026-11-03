from __future__ import annotations

import json
from pathlib import Path

import pytest

from mgsf.neural_behavior_intelligence import (
    explain_action,
    generate_holdout,
    inspect_episode,
    run_intelligence,
)
from mgsf.weight_space_game_ai import (
    Scenario,
    build_policy,
    load_fixture,
    repair_hazard_weights,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/weight-space/gridworld-v1.json"


def test_heldout_is_seeded_distinct_and_not_in_training() -> None:
    training = load_fixture(FIXTURE)
    a = generate_holdout(training, seed=12, count=40)
    b = generate_holdout(training, seed=12, count=40)
    assert a == b
    train_keys = {(s.size, s.start, s.goal, s.hazard) for s in training}
    hold_keys = {(s.size, s.start, s.goal, s.hazard) for s in a}
    assert len(a) == len(hold_keys) == 40
    assert not (train_keys & hold_keys)
    assert all(s.max_steps == s.size * s.size * 3 for s in a)


def test_heldout_changes_with_seed() -> None:
    training = load_fixture(FIXTURE)
    assert generate_holdout(training, seed=1) != generate_holdout(training, seed=2)


@pytest.mark.parametrize("count", [0, -1, 201])
def test_invalid_holdout_count_rejected(count: int) -> None:
    with pytest.raises(ValueError, match="count"):
        generate_holdout(load_fixture(FIXTURE), count=count)


def test_explanation_reconstructs_every_logit_exactly() -> None:
    s = Scenario("trace", 5, (0, 2), (4, 2), (2, 2), 18)
    before = build_policy()
    after, _ = repair_hazard_weights(before)
    for policy in [before, after]:
        explanation = explain_action(s, s.start, {s.start}, policy)
        assert len(explanation["actions"]) == 5
        for action in explanation["actions"]:
            assert len(action["features"]) == 5
            calculated = action["bias"] + sum(f["input"] * f["weight"] for f in action["features"])
            assert action["logit"] == pytest.approx(calculated)
            assert action["reconstructed_logit"] == pytest.approx(calculated)
        expected = max(enumerate(explanation["actions"]), key=lambda x: x[1]["logit"])[0]
        assert explanation["winner_index"] == expected


def test_repair_changes_hazard_attribution_not_other_features() -> None:
    s = Scenario("trace", 5, (1, 2), (4, 2), (2, 2), 18)
    baseline = build_policy()
    repaired, _ = repair_hazard_weights(baseline)
    first = explain_action(s, s.start, {s.start}, baseline)
    second = explain_action(s, s.start, {s.start}, repaired)
    before = first["actions"][-1]["features"]
    after = second["actions"][-1]["features"]
    assert before[1]["feature"] == after[1]["feature"] == "hazard"
    assert before[1]["contribution"] == 0
    assert after[1]["contribution"] == -30
    for j in (0, 2, 3, 4):
        assert before[j] == after[j]


def test_trace_matches_original_policy_actions() -> None:
    s = Scenario("trace", 5, (0, 2), (4, 2), (2, 2), 18)
    repaired, _ = repair_hazard_weights(build_policy())
    record = inspect_episode(s, repaired)
    assert record["outcome"] == "success"
    assert record["steps"] == len(record["trace"])
    assert all(entry["decision"]["position"] == entry["from"] for entry in record["trace"])


def test_evidence_viewer_and_handoff_are_reproducible(tmp_path: Path) -> None:
    a = run_intelligence(FIXTURE, tmp_path / "a", seed=123, count=20)
    b = run_intelligence(FIXTURE, tmp_path / "b", seed=123, count=20)
    assert a.read_bytes() == b.read_bytes()
    doc = json.loads(a.read_text(encoding="utf-8"))
    assert doc["promotion_gate"]["status"] == "HOLD"
    assert doc["real_game_measurement"] is False
    assert doc["training_or_optimization_performed"] is False
    assert doc["heldout_count"] == 20
    assert len(doc["evaluations"]["heldout/repaired"]["episodes"]) == 20
    assert len(doc["evaluations"]["training/unrepaired"]["episodes"]) == 12
    handoff = json.loads((tmp_path / "a/godot-handoff.json").read_text())
    assert handoff["execution_status"] == "not_executed"
    assert handoff["source"] == "python_deterministic_grid_simulator"
    assert handoff["policy"]["architecture"] == "linear_25_to_5"
    assert len(handoff["episodes"]) == 20
    html = (tmp_path / "a/neural-behavior-report.html").read_text()
    assert "<table>" in html
    assert "Promotion gate: HOLD" in html
    assert "<script" not in html


def test_small_holdout_is_deterministic(tmp_path: Path) -> None:
    out = run_intelligence(FIXTURE, tmp_path, seed=7, count=1)
    report = json.loads(out.read_text())
    assert report["evaluations"]["heldout/repaired"]["summary"]["episodes"] == 1
