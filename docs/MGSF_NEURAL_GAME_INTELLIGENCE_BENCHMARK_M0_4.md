# MGSF-WSP-M0.4: Neural Game Intelligence Benchmark

**Stage:** incubation. **Godot scope:** original rule kernel + authored 18 stages from [SHADOW SUM](https://github.com/madowaku/shadow-sum). **Promotion:** HOLD.

## Why this game

SHADOW SUM is an existing Godot 4.7 puzzle by madowaku. Its `src/shadow_rules.gd` implements the 5x5 puzzle exactly: each post casts one point to the south, west, and east. A stage is solved when the exact required post count is placed and all **visible** clue values match. `data/stages_v0_1.json` stores 18 authored stages with answers, but the AI is never given those answers.

This benchmark expands M0.3's stand-alone Godot fixture into **an authored game's actual core logic**. The existing title is not modified. Only the exact original `shadow_rules.gd` and stage data are copied into a temporary Godot runtime. The full SHADOW SUM UI, scene animation, click/tap input and game economy are **not run**.

## Fair comparison protocol

| Property | Rule-based greedy | Direct-weight scoring |
|---|---|---|
| Accessible input | Visible 5x5 clues, current posts, required post count | Same |
| Candidate actions | One post in any unused grid cell (25 maximum) | Same |
| Episode budget | Exactly the authored required post count | Same |
| Hidden stage `solution` | Never exported to planner | Never exported to planner |
| Decision | Lexicographic maximum of visible L1 error reduction, new exact visible clues, negative overshoots | Hand-written linear scoring of five public-derived features |
| Fitting / tuning | None | None |
| Tie break | Row-major | Row-major |
| Ground truth | Authored Godot ShadowRules | Same |

Direct policy features (per candidate): `visible_l1_reduction`, `new_exact_clues`, `overshot_clues`, `positive_clue_touches`, `visible_clue_touches`.

Direct policy static weights: `[2.0, 1.0, -4.0, 0.1, 0.0]`, with no bias. This is a 5-to-1 linear scoring neuron **repeated across 25 candidate post positions**. It is not the same 25-to-5 network as M0.1-M0.3; actions and game rules differ. The weights are manually authored and never updated by this experiment.

**Declared fixed split:** stages 001–006 = development; 007–018 = evaluation. Every stage is run under both methods. The latter are published, human-authored stages, not an unseen independent dataset. These split labels should not be mistaken for proof against dataset knowledge/tuning. Selection criteria and weights are fixed before evaluating in CI; do not retune based on these results and then call the same stages held out.

## Execute

Godot 4.7.2 and Python 3.11+; no paid service or AI API:

```bash
python -m pip install -e '.[dev]'
git clone https://github.com/madowaku/shadow-sum vendor/shadow-sum
git -C vendor/shadow-sum checkout 12655b88f8937698f832e9572fdfb8a4912358b7
mgsf neural-game-benchmark vendor/shadow-sum --godot /path/to/godot --output-root evidence
pytest -q tests/test_neural_game_benchmark.py
```

CI checks out the pinned commit and runs the same command. The script copies only two original authored files into a `TemporaryDirectory`, launches the real Godot executable with `--headless --script`, validates hashes and replay outcomes, then removes the temporary project. No files are written into the original game checkout.

## Evidence

`evidence/shadow-sum-neural-benchmark/` contains:

- `policy-plans.json`: complete stage inputs without `solution`, all placements, public features, scores, fixed weights, equal budgets, exact source hashes
- `godot-results.json`: emitted by Godot using original `ShadowRules.compute_shadow`, `matches_visible_clues` and `count_posts` for every policy/stage pair
- `godot-runtime.log`: actual engine stdout/stderr, exit code, completion marker
- `shadow-sum-neural-benchmark-evidence.json`: source commit and SHA-256, per-stage wins/errors, split summaries, internal parity checks, artifact hashes, PASS/FAIL, promotion HOLD

Each policy is rated on the same authored stages using:
1. **Solved**: exact required posts and all visible clues match (authoritative Godot judgement)
2. **Visible L1 error**: sum of absolute differences for visible clues only
3. **Failure index**: record the exact stage IDs and selected actions to inspect policy blind spots

Only a clean engine run with a valid result, exact source SHA, equal budgets, and **all 36 paired records** passing independent Python replay checks can earn **runtime status=PASS**. No particular policy is guaranteed to outperform the other.

`promotion_gate.status=HOLD` remains unconditional: a known authored stage pack, static hand-written weights and headless rules-only runtime do not demonstrate actual game UI play, out-of-distribution generalization, or improved player experience.

## First CI observation (pinned 18-stage pack)

After both fixed policies were executed under the original Godot rule kernel:

| Split | Rule greedy solved | Direct weights solved | Placement-sequence disagreements |
|---|---:|---:|---:|
| Development 001–006 | 6/6 | 6/6 | 0/6 |
| Evaluation 007–018 | 11/12 | 11/12 | 0/12 |

Both fail **stage 008** with visible-clue L1 error **2**. Every selected post sequence was identical across all 18 stages. This benchmark therefore **does not establish any neural advantage or a distinct learned policy**. It validates a reproducible, paired evaluation and reveals that the hand-written linear scorer currently mimics the simple greedy rule. This observation motivated recording `paired_outcomes` and disagreement metrics.

## Roadmap

Next step is an actual click/tap automation adapter to SHADOW SUM's authored UI with screenshots of the original scene, frame hashes, and runtime error monitoring. Also add a genuinely blind stage pack generated after policy freeze and a stronger search/backtracking baseline before asserting comparative intelligence. This service should remain incubation until then.
