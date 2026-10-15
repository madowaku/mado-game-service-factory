# MGSF-M0.9.1 - Expert Skill A/B Benchmark / Real Gameplay Quality Gate

## Scope and claim discipline

This milestone compares a **control arm without external GDAS skill guidance** against a **treatment arm with one reviewed, pinned M0.9 Godot skill**. It outputs an A/B experiment plan, executes identical Godot test scripts against two *different* clean Git checkouts, and ingests MGSF's existing **direct Godot capture** adapter reports. It neither implements the game automatically nor auto-installs third-party code.

**No fixture, plan, agent self-report, stdout-only test, or single experimental run can trigger PROMOTE.** The result stays `HOLD` (incomplete) or `REVIEW` (machine-evidence complete, human assessment still required), always with `promotion_status: HOLD` and `causal_claim_supported: false`.

## Setup

First produce a M0.9 route for the exact task:

```bash
mgsf skill-route fixtures/agent-skills/gyro-lab-puzzle.json \
  --output-root evidence/agent-skills

mgsf skill-ab-plan fixtures/agent-skills/gyro-puzzle-ab.json \
  evidence/agent-skills/gyro-lab-puzzle-m09/skill-route.json \
  --output-root evidence/skill-ab
```

The initial fixture plans only. Its `test_script` path is a required implementation contract, **not** a claim that the script already exists in `vertical-slice`. The example baseline SHA must be updated for an actual puzzle project.

The generator emits:

- `experiment.json` with pinned baseline SHA, seed, required test assertions, selected skill URL and source SHA
- `control-PROMPT.md` and `treatment-PROMPT.md` with identical tasks, test cases, engine version and seed. The sole intended difference is whether independently reviewed third-party guidance is available.

Run Codex twice in isolated worktrees created from the *same baseline commit*. Keep generation budgets, model, tests, and prompt variants consistent. Avoid cross-arm contamination. Preserve Codex run logs as separate supporting provenance. Do not merge the arms or modify shared test assertions.

## Real Godot runner

Write the **same independently reviewed** Godot SceneTree test script in both project checkouts, commit both implementations, and ensure clean Git status.

The test must **actually drive game logic**. A script that merely prints PASS strings is invalid test design and must be rejected by human review.

Godot is called once per checkout:

```text
godot --headless --path <checkout> --script res://tests/ab_scenario.gd -- --mgsf-seed=42
```

The script reads the seed from user args and prints the seed **after applying it**:

```text
MGSF_SEED:42
MGSF_ASSERT:undo:PASS
MGSF_ASSERT:victory:FAIL
```

Assertion IDs must be exactly those listed in the experiment. Duplicates, missing/unrecognized IDs, missing/mismatched seed echo, non-zero engine exits, timeouts, and modified test scripts block the comparison.

For the current directly supported C6 capture scene, create *separate* direct capture reports in each arm with the M0.3b adapter:

```bash
mgsf godot-capture <control-checkout> --godot <Godot-binary> --xvfb \
  --output-root evidence/ab-control-capture
mgsf godot-capture <treatment-checkout> --godot <Godot-binary> --xvfb \
  --output-root evidence/ab-treatment-capture
```

Use `--xvfb` only on Linux with xvfb installed. Existing `godot-capture` is C6-scene-specific; new puzzle projects need a compatible direct capture scene/adapter before they can produce eligible A/B evidence. No synthetic SVG frames or screenshots claimed by an agent may substitute.

Run the A/B benchmark:

```bash
mgsf skill-ab-run evidence/skill-ab/gyro-puzzle-ab-001/experiment.json \
  <control-checkout> <treatment-checkout> --godot <Godot-binary> \
  --control-capture-eval evidence/ab-control-capture/godot-capture-adapter/vertical-slice-c6-direct/adapter_eval.json \
  --treatment-capture-eval evidence/ab-treatment-capture/godot-capture-adapter/vertical-slice-c6-direct/adapter_eval.json \
  --output-root evidence/skill-ab-runs
```

Each arm writes `stdout.log`, `stderr.log`, `run.json`, including Git HEAD, source SHA, test script SHA, Godot command and return code, duration, output hashes, parsed assertions and direct PNG evidence checksums.

Combined `benchmark.json` records the assertion PASS delta and one of three comparative outcomes only when both arms have **real direct capture provenance** and complete, successful runner evidence:

- `TREATMENT_BETTER_ON_ASSERTIONS`
- `CONTROL_BETTER_ON_ASSERTIONS`
- `TIED_ON_ASSERTIONS`

Otherwise: `HOLD / INSUFFICIENT_REAL_EVIDENCE`.

## Quality gate and limitations

The runner verifies both projects are descendants of the same pinned Git baseline, clean, separate worktrees, identical reviewed test-script bytes, the same engine binary and observed version, and the same argument seed. It hashes artifacts and cross-checks existing MGSF direct Godot capture metadata, required M0.3b criteria, input/result timeline and PNG signatures. It does not automatically validate the scientific fairness of the Codex runs, independently prove GDAS guidance was actually applied, cryptographically attest the Godot executable, or bind the separate capture run to the exact test process invocation.

A successful test script can still be weak or deceptive. A source-hash match does not independently verify the test's correctness. Human review of tests, screenshots, input replay, skill license, and source provenance is mandatory. Compare *several preregistered seeds and tasks* before making a directional or causal claim. Runtime assertions are test outcomes, not human game-feel measurements.

No changes to EdenSpark M0.6-M0.8 promotion; no automated publishing or external uploads.
