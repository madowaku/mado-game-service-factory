from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mgsf.neural_game_benchmark import (
    DEVELOPMENT_IDS, EVALUATION_IDS, FEATURES, POLICIES, WEIGHTS, Stage,
    _feature_vector, build_plan, choose_posts, load_public_stages, shadow,
    validate_game_trace, visible_error, paired_outcomes,
)


def _sample_pack(tmp_path: Path) -> Path:
    stages = []
    for sid in range(1, 19):
        stages.append({
            "id": sid,
            "title": "sample",
            "tier": "sample",
            "posts": 1,
            "clues": [[-1] * 5 for _ in range(5)],
            "solution": ["SECRET MUST NOT LEAK"],
        })
    target = tmp_path / "stages.json"
    target.write_text(json.dumps(stages), encoding="utf-8")
    return target


def _mock_verified_engine(plan: dict) -> dict:
    stages = []
    for item in plan["stage_inputs"]:
        records = {}
        for name in POLICIES:
            cells = [entry["cell"] for entry in item["plans"][name]["placements"]]
            calculated = shadow({tuple(cell) for cell in cells})
            wins = len(cells) == item["posts"] and all(
                item["clues"][r][c] < 0 or item["clues"][r][c] == calculated[r][c]
                for r in range(5) for c in range(5)
            )
            records[name] = {
                "placements": cells, "shadow": [list(row) for row in calculated],
                "placed_count": len(cells), "success": wins,
                "visible_l1_error": visible_error(item["clues"], calculated),
            }
        stages.append({"id": item["id"], "policies": records})
    return {
        "schema_version": 1,
        "source_stage_sha256": plan["source_stage_sha256"],
        "source_rules_sha256": plan["source_rules_sha256"],
        "stages": stages,
    }


def test_original_shadow_rules_geometry() -> None:
    result = shadow({(1, 2)})
    assert result[2][2] == 1   # south
    assert result[1][1] == 1   # west
    assert result[1][3] == 1   # east
    assert sum(sum(row) for row in result) == 3


def test_public_stage_loader_discards_solution(tmp_path: Path) -> None:
    path = _sample_pack(tmp_path)
    records = load_public_stages(path)
    assert len(records) == 18
    assert all(not hasattr(stage, "solution") for stage in records)
    assert records[0].clues[0][0] == -1


def test_both_policies_get_same_budget_and_public_features(tmp_path: Path) -> None:
    stage = load_public_stages(_sample_pack(tmp_path))[0]
    for policy in POLICIES:
        plan = choose_posts(stage, policy)
        assert len(plan["placements"]) == stage.posts
        assert len({tuple(item["cell"]) for item in plan["placements"]}) == stage.posts
        assert len(plan["placements"][0]["features"]) == len(FEATURES) == len(WEIGHTS)


def test_candidate_features_only_depend_on_public_stage_and_board() -> None:
    clue_rows = [[0] * 5 for _ in range(5)]
    clue_rows[1][1] = 1
    stage = Stage(1, 1, tuple(tuple(row) for row in clue_rows))
    before = visible_error(stage.clues, shadow(set()))
    values = _feature_vector(stage, set(), (1, 2))
    after = visible_error(stage.clues, shadow({(1, 2)}))
    assert values[0] == before - after
    assert values[2] >= 0


def test_plan_contains_no_solution_keys_and_splits_are_disjoint(tmp_path: Path) -> None:
    stages = load_public_stages(_sample_pack(tmp_path))
    planned = build_plan(stages, "stage_digest", "rule_digest")
    serialized = json.dumps(planned)
    assert '"solution":' not in serialized
    assert "SECRET MUST NOT LEAK" not in serialized
    assert set(DEVELOPMENT_IDS).isdisjoint(EVALUATION_IDS)
    assert planned["evaluation_ids"] == list(range(7, 19))
    assert planned["direct_weights"] == list(WEIGHTS)


def test_plan_is_reproducible(tmp_path: Path) -> None:
    stages = load_public_stages(_sample_pack(tmp_path))
    assert build_plan(stages, "a", "b") == build_plan(stages, "a", "b")


def test_mock_trace_validation_checks_all_paired_outputs(tmp_path: Path) -> None:
    plan = build_plan(load_public_stages(_sample_pack(tmp_path)), "source", "rules")
    engine = _mock_verified_engine(plan)
    errors, summary = validate_game_trace(plan, engine)
    assert errors == []
    assert summary["development"]["rule_greedy"]["stages"] == 6
    assert summary["development"]["direct_weights"]["stages"] == 6
    assert summary["evaluation"]["rule_greedy"]["stages"] == 12
    assert summary["evaluation"]["direct_weights"]["stages"] == 12


@pytest.mark.parametrize(
    "mutate,keyword",
    [
        (lambda r: r.update({"source_rules_sha256": "tampered"}), "source hashes"),
        (lambda r: r["stages"][0]["policies"]["direct_weights"].update({"success": False}), "engine win differs"),
        (lambda r: r["stages"][0]["policies"]["rule_greedy"].update({"visible_l1_error": 15}), "engine error differs"),
        (lambda r: r["stages"][0]["policies"]["rule_greedy"].update({"shadow": [[7] * 5 for _ in range(5)]}), "shadow"),
        (lambda r: r["stages"][0]["policies"]["direct_weights"].update({"placements": [[4, 4], [3, 3]]}), "actions differ"),
        (lambda r: r["stages"].pop(), "count differs"),
    ],
)
def test_tampered_godot_result_rejected(tmp_path: Path, mutate, keyword: str) -> None:
    plan = build_plan(load_public_stages(_sample_pack(tmp_path)), "source", "rules")
    trace = _mock_verified_engine(plan)
    mutate(trace)
    errors, _ = validate_game_trace(plan, trace)
    assert any(keyword in problem for problem in errors), errors


@pytest.mark.parametrize(
    "invalid",
    [
        {"id": 1, "posts": True},
        {"id": 1, "posts": 0},
        {"id": 1, "clues": [[0] * 5] * 4},
        {"id": 1, "clues": [[4] * 5] * 5},
    ],
)
def test_invalid_public_stage_rejected(tmp_path: Path, invalid: dict) -> None:
    path = _sample_pack(tmp_path)
    stages = json.loads(path.read_text())
    stages[0].update(invalid)
    path.write_text(json.dumps(stages), encoding="utf-8")
    with pytest.raises(ValueError):
        load_public_stages(path)


def test_missing_stage_rejected(tmp_path: Path) -> None:
    path = _sample_pack(tmp_path)
    stages = json.loads(path.read_text())
    stages.pop()
    path.write_text(json.dumps(stages), encoding="utf-8")
    with pytest.raises(ValueError, match="eighteen"):
        load_public_stages(path)


def test_paired_outcomes_report_identical_behavior_as_zero_divergence(tmp_path: Path) -> None:
    plan = build_plan(load_public_stages(_sample_pack(tmp_path)), "source", "rules")
    engine = _mock_verified_engine(plan)
    errors, summary = validate_game_trace(plan, engine)
    assert errors == []
    paired = paired_outcomes(summary)
    assert paired["development"]["stages"] == 6
    assert paired["evaluation"]["stages"] == 12
    assert paired["development"]["different_action_sequences"] == 0
    assert paired["evaluation"]["different_action_sequences"] == 0
    assert paired["evaluation"]["both_solved"] == 12


def test_paired_outcomes_detect_policy_divergence() -> None:
    base = [{"stage_id": 1, "actions": [[0, 0]], "success": True}]
    different = [{"stage_id": 1, "actions": [[0, 1]], "success": False}]
    output = paired_outcomes({
        "evaluation": {
            "rule_greedy": {"results": base},
            "direct_weights": {"results": different},
        }
    })
    assert output["evaluation"]["different_action_sequences"] == 1
    assert output["evaluation"]["action_disagreement_rate"] == 1.0
    assert output["evaluation"]["rule_only_solved"] == 1
    assert output["evaluation"]["direct_weights_only_solved"] == 0


def test_unknown_policy_rejected(tmp_path: Path) -> None:
    stage = load_public_stages(_sample_pack(tmp_path))[0]
    with pytest.raises(ValueError):
        choose_posts(stage, "omniscient")
