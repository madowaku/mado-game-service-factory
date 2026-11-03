# MGSF-WSP-M0.1: Weight-Space Game AI Lab (incubation)

## Goal

Test a tiny, reproducible version of **direct neural-weight construction and repair** as a game-development service. This is a **new, independently authored educational implementation**, inspired by Rikiya Takehi et al., *Sparks of Weight-Space Programming* (November 2, 2026). It **does not reproduce** the MinAtar/Go results or use an LLM to create weights.

Research: https://rikiyat.github.io/blog/weight-space-programming/  
Original experiment logs: https://github.com/RikiyaT/lm_understand-logs

## M0.1 contract

```text
fixed JSON grid scenarios
  -> hand-write a sparse linear policy (25 inputs -> 5 action logits)
  -> seeded random baseline + original policy evaluation
  -> direct edit of 5 hazard-related weight coefficients
  -> repaired policy evaluation on identical scenarios
  -> JSON evidence with full action traces and weight diff
  -> promotion gate: HOLD (fixture only)
```

The 5x5 grid has a start, goal, and lethal hazard. Each action observes only five local features: goal-distance progress, whether its next tile is hazardous, wall collision, visited tile, and whether it is no-op. The same feature set is repeated for each of five actions, yielding 25 inputs and an affine layer with 130 parameters (125 weights plus 5 biases).

**The feature extractor itself exposes hazard information**. Repairing the five hazard coefficients from `0` to `-30` is therefore an intentionally simple proof that a small weight patch changes policy behavior. It is not evidence of emergent hazard discovery, interpretation of an arbitrary trained network, or transferable LLM weight-editing skill. No gradients, fitting, optimizers, API keys, or GPU are used.

## Run

From the repository root with Python 3.11+:

```bash
python -m pip install -e '.[dev]'
mgsf weight-space-eval fixtures/weight-space/gridworld-v1.json --output-root evidence/weight-space
python -m pytest tests/test_weight_space_game_ai.py -q
```

Output: `evidence/weight-space/weight-space-game-ai-evidence.json` (the evidence directory is gitignored).

Included evidence:
- `source_fixture_sha256` and the exact scenario list in the source JSON
- complete weight matrices and hashes for both policies
- explicit `weight_edits` (action, row, column, before, after)
- random, unrepaired, and repaired summaries with full movement traces
- `evidence_class=deterministic_weight_space_fixture`, `trained=false`, `uses_gradients=false`
- `promotion_gate.status=HOLD` regardless of fixture outcomes

## M0.1 observed result

For the 12 deliberately selected example episodes:

| Policy | Successes | Hazard failures | Timeouts |
|---|---:|---:|---:|
| Seeded random | 1/12 | 4 | 7 |
| Original sparse policy (hazard coefficient 0) | 4/12 | 8 | 0 |
| Repaired sparse policy (five hazard coefficients -30) | 12/12 | 0 | 0 |

These are **in-sample, deliberately curated deterministic cases**, not independent trials, statistical estimates, research-reproduction results, or real-player/game results. The repair and test tasks were chosen together. A policy that merely encodes the known safety rule should do well here.

## Evaluation and promotion boundary

- Fixture success verifies the contract and regression behavior only.
- `HOLD` remains mandatory until a **real game adapter** supplies provenance-preserving runtime traces, an independent unseen-scenario evaluation, and comparisons against non-neural rule-based baselines.
- Neither synthetic fixture frames nor policy traces are direct captured game video.
- Weight patch review must list every changed element and preserve the original policy.
- Do not claim that this lab beats PPO, is equivalent to the MIT experiments, or uses Astra to edit networks.

## Next experiment (not implemented)

1. Introduce generated **held-out** scenarios, including layouts with walls, multiple hazards, and cases where greedy progress fails.
2. Add a JSON-compatible GameAdapter to test an actual Godot project, with media/hash provenance delegated to existing MGSF capture services.
3. Compare fixed rules, hand-written weights, a small trained baseline, and an LLM-proposed patch under the **same** test set and compute budget.
4. Only then explore LLM-assisted weights, with numerical bounds, deterministic validation, versioned patches, and human review. No automatic merge/deploy.

No existing service changes lifecycle stage as a result of this lab.
