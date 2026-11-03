from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mgsf.godot_neural_bridge import _compare_trace, _png_is_real_frame, load_handoff
from mgsf.neural_behavior_intelligence import inspect_episode, run_intelligence
from mgsf.weight_space_game_ai import ACTIONS, FEATURES, Scenario, build_policy, repair_hazard_weights


TRAINING = Path(__file__).resolve().parents[1] / "fixtures/weight-space/gridworld-v1.json"


def _handoff(tmp_path: Path) -> Path:
    run_intelligence(TRAINING, tmp_path / "generated", seed=57, count=8)
    return tmp_path / "generated" / "godot-handoff.json"


def test_handoff_loads_exact_neural_policy_and_games(tmp_path: Path) -> None:
    path = _handoff(tmp_path)
    contract, policy, episodes = load_handoff(path)
    assert contract["execution_status"] == "not_executed"
    assert contract["feature_order"] == list(FEATURES)
    assert len(episodes) == 8
    assert len(policy.weights) == len(ACTIONS) == 5
    assert len(policy.weights[0]) == 25
    assert policy.weights[4][21] == -30.0


@pytest.mark.parametrize(
    "alter",
    [
        lambda obj: obj.update({"schema_version": 2}),
        lambda obj: obj.update({"execution_status": "completed"}),
        lambda obj: obj.update({"feature_order": list(reversed(obj["feature_order"]))}),
        lambda obj: obj["action_deltas"].update({"left": [1, 0]}),
        lambda obj: obj["policy"].update({"architecture": "opaque"}),
        lambda obj: obj["episodes"][0].update({"goal": obj["episodes"][0]["start"]}),
        lambda obj: obj["episodes"][0].update({"max_steps": True}),
        lambda obj: obj["episodes"].append(dict(obj["episodes"][0])),
    ],
)
def test_malformed_handoff_rejected(tmp_path: Path, alter) -> None:
    path = _handoff(tmp_path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    alter(obj)
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError):
        load_handoff(path)


def test_oracle_matches_valid_identical_record() -> None:
    s = Scenario("oracle", 5, (0, 2), (4, 2), (2, 2), 18)
    repaired, _ = repair_hazard_weights(build_policy())
    record = inspect_episode(s, repaired)
    actual = {
        "scenario_id": record["scenario_id"],
        "outcome": record["outcome"],
        "steps": record["steps"],
        "trace": [
            {
                "step": step["step"], "from": step["from"], "to": step["to"],
                "wall": step["wall"],
                "decision": {
                    "winner": step["decision"]["winner"],
                    "winner_index": step["decision"]["winner_index"],
                    "logits": [entry["logit"] for entry in step["decision"]["actions"]],
                },
            } for step in record["trace"]
        ],
    }
    assert _compare_trace(record, actual) == []
    corrupt = deepcopy(actual)
    corrupt["trace"][0]["decision"]["logits"][4] += 3
    assert any("logit 4 differs" in error for error in _compare_trace(record, corrupt))
    corrupt = deepcopy(actual)
    corrupt["trace"][0]["to"] = [4, 4]
    assert any("to differs" in error for error in _compare_trace(record, corrupt))
    corrupt = deepcopy(actual)
    corrupt["outcome"] = "hazard"
    assert any("outcome differs" in error for error in _compare_trace(record, corrupt))


def test_missing_and_truncated_screenshot_rejected(tmp_path: Path) -> None:
    image = tmp_path / "before.png"
    assert not _png_is_real_frame(image)
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert not _png_is_real_frame(image)
