"""M0.2 neural behavior intelligence: held-out cases and exact linear attributions.

Every explanation is computed as a decomposition of the policy's actual logit,
not a natural-language guess about model reasoning. All gameplay here is a
deterministic grid simulation, including the Godot handoff contract.
"""

from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from pathlib import Path
import random
from typing import Any

from .weight_space_game_ai import (
    ACTIONS, FEATURES, Scenario, LinearPolicy, build_policy, load_fixture,
    observe, repair_hazard_weights, _summary,
)


def generate_holdout(
    training: list[Scenario], *, seed: int = 20261103, count: int = 40
) -> list[Scenario]:
    """Generate untouched evaluation scenarios with no exact training-layout duplicates."""
    if not 1 <= count <= 200:
        raise ValueError("count must be 1..200")
    rng = random.Random(seed)
    occupied = {(s.size, s.start, s.goal, s.hazard) for s in training}
    cases: list[Scenario] = []
    attempts = 0
    while len(cases) < count:
        attempts += 1
        if attempts > 20000:
            raise ValueError("unable to generate enough distinct held-out cases")
        size = rng.choice((4, 5, 6, 7))
        positions = [(x, y) for y in range(size) for x in range(size)]
        start, goal, hazard = rng.sample(positions, 3)
        identifier = (size, start, goal, hazard)
        if identifier in occupied:
            continue
        occupied.add(identifier)
        cases.append(Scenario(
            id=f"heldout-{seed}-{len(cases):03d}",
            size=size,
            start=start,
            goal=goal,
            hazard=hazard,
            max_steps=3 * size * size,
        ))
    return cases


def explain_action(
    scenario: Scenario,
    position: tuple[int, int],
    visited: set[tuple[int, int]],
    policy: LinearPolicy,
) -> dict[str, Any]:
    """Exact attribution for each output logit: bias + sum(W_ij * x_j)."""
    inputs = observe(scenario, position, visited)
    scores = policy.logits(inputs)
    decisions: list[dict[str, Any]] = []
    for index, (action, _) in enumerate(ACTIONS):
        offset = index * len(FEATURES)
        features = [
            {
                "feature": name,
                "input": inputs[offset + j],
                "weight": policy.weights[index][offset + j],
                "contribution": inputs[offset + j] * policy.weights[index][offset + j],
            }
            for j, name in enumerate(FEATURES)
        ]
        reconstructed = policy.bias[index] + sum(row["contribution"] for row in features)
        if abs(reconstructed - scores[index]) > 1e-9:
            raise AssertionError("attribution did not reconstruct logit")
        decisions.append({
            "action": action,
            "logit": scores[index],
            "bias": policy.bias[index],
            "features": features,
            "reconstructed_logit": reconstructed,
        })
    winner = max(range(len(scores)), key=lambda i: scores[i])
    return {
        "position": list(position),
        "winner": ACTIONS[winner][0],
        "winner_index": winner,
        "tie_break": "first action in ACTIONS order",
        "actions": decisions,
    }


def inspect_episode(scenario: Scenario, policy: LinearPolicy) -> dict[str, Any]:
    position = scenario.start
    visited = {position}
    events: list[dict[str, Any]] = []
    outcome = "timeout"
    for step in range(1, scenario.max_steps + 1):
        decision = explain_action(scenario, position, visited, policy)
        idx = decision["winner_index"]
        _, (dx, dy) = ACTIONS[idx]
        dest = (position[0] + dx, position[1] + dy)
        wall = not (0 <= dest[0] < scenario.size and 0 <= dest[1] < scenario.size)
        if wall:
            dest = position
        events.append({
            "step": step,
            "from": list(position),
            "to": list(dest),
            "wall": wall,
            "decision": decision,
        })
        position = dest
        visited.add(position)
        if position == scenario.hazard:
            outcome = "hazard"
            break
        if position == scenario.goal:
            outcome = "success"
            break
    return {"scenario_id": scenario.id, "outcome": outcome, "steps": len(events), "trace": events}


def _render_html(report: dict[str, Any]) -> str:
    """Standalone dependency-free viewer; no Javascript and all data escaped."""
    sections = []
    for name, result in report["evaluations"].items():
        rows = []
        for entry in result["episodes"]:
            # Keep detailed traces in JSON; show a succinct index and first decision here.
            first = entry["trace"][0]["decision"] if entry["trace"] else None
            scores = ", ".join(
                f"{a['action']}={a['logit']:g}" for a in first["actions"]
            ) if first else "no steps"
            rows.append(
                "<tr><td>" + escape(entry["scenario_id"]) +
                "</td><td>" + escape(entry["outcome"]) +
                "</td><td>" + str(entry["steps"]) +
                "</td><td>" + escape(first["winner"] if first else "") +
                "</td><td>" + escape(scores) + "</td></tr>"
            )
        summary = result["summary"]
        sections.append(
            f"<section><h2>{escape(name)}</h2>"
            f"<p>Success: {summary['successes']}/{summary['episodes']} "
            f"| Hazard: {summary['hazard_failures']} "
            f"| Timeout: {summary['timeouts']}</p>"
            "<table><thead><tr><th>Episode</th><th>Outcome</th>"
            "<th>Steps</th><th>First action</th><th>First-step logits</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></section>"
        )
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>MGSF Neural Behavior Intelligence M0.2</title>"
        "<style>body{font:15px system-ui,sans-serif;max-width:1150px;margin:2em auto;"
        "padding:0 1em;background:#101522;color:#ecf1fa}section{margin:2em 0}"
        "table{border-collapse:collapse;width:100%;font-size:.84em}"
        "th,td{border-bottom:1px solid #465068;padding:.55em;text-align:left}"
        "th{color:#aaceff}p,small{color:#bac8d9}</style>"
        "<h1>Neural Behavior Intelligence / M0.2</h1>"
        "<p>Exact linear-logit decomposition, not an explanation of hidden thoughts. "
        "Generated held-out grid fixtures only. Promotion gate: HOLD.</p>"
        + "".join(sections)
        + "<p>For every action, see the evidence JSON: logit = bias + "
        "sum(input × weight). The viewer displays only the first-step logits.</p>"
        "</html>"
    )


def run_intelligence(
    training_fixture: str | Path,
    output_root: str | Path,
    *,
    seed: int = 20261103,
    count: int = 40,
) -> Path:
    source_path = Path(training_fixture)
    training = load_fixture(source_path)
    heldout = generate_holdout(training, seed=seed, count=count)
    original = build_policy()
    repaired, edits = repair_hazard_weights(original)
    cases = {"training": training, "heldout": heldout}
    evaluations: dict[str, Any] = {}
    for split, scenarios in cases.items():
        for label, policy in (("unrepaired", original), ("repaired", repaired)):
            episodes = [inspect_episode(s, policy) for s in scenarios]
            evaluations[f"{split}/{label}"] = {
                "summary": _summary(episodes),
                "episodes": episodes,
            }
    # Neutral JSON boundary for a future Godot GameAdapter.
    # This file is NOT evidence that Godot ran these policies.
    godot_contract = {
        "schema_version": 1,
        "contract_kind": "godot_gridworld_handoff",
        "execution_status": "not_executed",
        "source": "python_deterministic_grid_simulator",
        "coordinate_system": "x increases right; y increases down",
        "action_deltas": {name: list(delta) for name, delta in ACTIONS},
        "feature_order": list(FEATURES),
        "policy": repaired.as_dict(),
        "episodes": [
            {
                "id": s.id, "size": s.size, "start": list(s.start),
                "goal": list(s.goal), "hazard": list(s.hazard),
                "max_steps": s.max_steps,
            }
            for s in heldout
        ],
    }
    report = {
        "schema_version": 1,
        "milestone": "MGSF-WSP-M0.2",
        "service": "neural-behavior-intelligence",
        "evidence_class": "deterministic_neural_behavior_fixture",
        "real_game_measurement": False,
        "training_or_optimization_performed": False,
        "heldout_layouts_not_seen_during_patch": True,
        "heldout_protocol": "seeded randomized distinct layouts, not independent environments",
        "training_fixture_sha256": sha256(source_path.read_bytes()).hexdigest(),
        "heldout_seed": seed,
        "heldout_count": count,
        "weight_edits": edits,
        "policy": {"unrepaired": original.as_dict(), "repaired": repaired.as_dict()},
        "evaluations": evaluations,
        "godot_handoff": "godot-handoff.json",
        "promotion_gate": {
            "status": "HOLD",
            "reason": "Python fixture-only; Godot handoff has not been executed, "
                      "and independent real-game comparison is still required",
        },
    }
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "godot-handoff.json").write_text(
        json.dumps(godot_contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "neural-behavior-report.html").write_text(
        _render_html(report), encoding="utf-8"
    )
    destination = root / "neural-behavior-evidence.json"
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination
