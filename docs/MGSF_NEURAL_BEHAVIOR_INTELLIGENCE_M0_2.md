# MGSF-WSP-M0.2: Neural Behavior Intelligence

**Status:** incubation / fixture-only / HOLD. M0.2 builds on the unmerged M0.1 branch, not main. All metrics describe the deliberately simple Python grid simulator.

## Scope

1. Produce seeded held-out grid layouts distinct from the 12 selected M0.1 examples. They are held out from the *hand-authored patch*, but share the exact environment and five features. This is a limited generalization check, not a new game or broad out-of-distribution proof.
2. For every step and every candidate action, record an **exact affine-layer decomposition**: `logit = bias + sum(feature input * corresponding weight)`. This is a numerical audit of this transparent model, not an LLM-generated story of why a complex network chose an action.
3. Export three artifacts: `neural-behavior-evidence.json` (full traces), `neural-behavior-report.html` (offline summary dashboard), and `godot-handoff.json` (portable action/feature/policy/scenario contract).
4. Hold promotion until a real Godot runtime has executed the actual policy in a real project, with source/runtime artifact provenance and a comparison against a non-neural baseline.

## Run

```bash
python -m pip install -e '.[dev]'
mgsf neural-behavior-eval fixtures/weight-space/gridworld-v1.json --seed 20261103 --count 40 --output-root evidence/neural-behavior
pytest -q tests/test_neural_behavior_intelligence.py
```

The HTML viewer is local-only and does not load third-party scripts or fonts.

## Explicit safety and provenance

- `real_game_measurement=false`: the simulations run in Python, not Godot.
- `godot-handoff.json.execution_status=not_executed`: this is a **contract** for a future Godot adapter, not a proof of interoperability.
- `training_or_optimization_performed=false`: the held-out cases do not alter weights.
- `promotion_gate.status=HOLD`: always HOLD, even when every held-out case succeeds.
- Randomized layouts are filtered for exact duplicates against training examples. They still sample from the same gridworld distribution, share the same observation representation, and do not test hidden hazards, walls, or adversarial layouts.
- Policy attribution relies on direct access to the explicit 25-to-5 affine weight matrix; it does not constitute a general mechanistic interpretability method for arbitrary models.

## Next proof gate

Connect a Godot `GameAdapter` to the exact exported policy and compare serialized action traces with Python. Capture Godot runtime logs and direct screenshots via MGSF's existing provenance-capable capture tools. Build new *structurally different* scenarios and compare fixed rules / learned policy / weight patches fairly. Only then decide whether to upgrade the service from incubation.
