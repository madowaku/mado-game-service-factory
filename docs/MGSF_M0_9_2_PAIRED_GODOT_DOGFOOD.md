# MGSF-M0.9.2 - Paired Godot Dogfood / Skill Effectiveness Evidence

## Purpose and strict interpretation

MGSF now has a way to record *real* paired Godot test runs (M0.9.1) and to track whether both implementations actually had comparable, recorded Codex sessions with or without the selected external Godot expert skill (M0.9.2).

The M0.9.2 CI **neutral A/B smoke** creates two independent Git clones of the pinned public `madowaku/vertical-slice` commit `f0514229d7f2036ec25646d09e3647c8d870dadb`. It copies the same independently authored Godot scenario into both, commits both, runs Godot headlessly and captures two sets of actual rendered PNGs with existing M0.3b. Since the game code and instructions are **identical**, it is a **paired infrastructure proof**, NOT a skill-effectiveness experiment. Both Godot arms can be REVIEW while M0.9.2 properly says HOLD because there are **no genuine treatment/control Codex implementation receipts**.

One successful real A/B with different revisions and valid receipts is still **REVIEW**, never proof that one skill improves game quality or cause-effect. Publication and prototype promotion remain explicitly disabled. No automatic upstream skill download or install.

## CI neutral dogfood

```bash
bash scripts/run_vertical_slice_ab_smoke.sh \
  /tmp/godot/Godot_v4.7.2-stable_linux.x86_64 \
  ci-evidence/paired-godot-neutral-smoke
```

CI uses existing pinned `vendor/vertical-slice` and `xvfb-run`. The script prepares two clones, installs a **test fixture** in each (never an external skill), computes M0.9 selection for `godot-testing-patterns`, creates a M0.9.1 plan, obtains independent C6 direct capture reports and runs three objective Godot state suites:

- `playfeel`: C6 round and near-miss/reveal behavior
- `blind_privacy`: blind-view projection does not reveal secret game state
- `sensor_logic`: truthful private sensor rules

The fixed script uses the supplied random seed, executes the pre-existing real Godot test suites, then prints explicit MGSF assertion lines. Its source file is checked in as `fixtures/agent-skills/vertical-slice-ab-scenario.gd` so both arms receive the *same audited bytes*. Neutral results must be three PASS assertions in both arms, delta 0, and valid rendered capture proof.

## Actual Codex control/treatment procedure

An actual quality experiment needs two **fresh, isolated clean Git checkouts at the pinned baseline**, exactly the same model and execution budget, and reviewed, recorded Codex execution for both.

1. Generate M0.9 route with `mgsf skill-route fixtures/agent-skills/vertical-slice-testing-request.json`. Generate the experiment plan from `fixtures/agent-skills/vertical-slice-c6-ab.json` and the route.
2. Review the exact upstream LGPL-3.0 `godot-testing-patterns/SKILL.md` at the commit pinned in the route. Store an independently reviewed local copy, calculate SHA-256 with `sha256sum` or `Get-FileHash`. Never auto-run embedded code or install all upstream skills.
3. Use the commands below for each separate checkout. The tool **does not commit changes**; inspect each generated diff, remove errors and manually commit each implementation. Keep the reference test script byte-identical in both checkouts.
4. Capture both real games via the existing M0.3b adapter, execute M0.9.1 with `skill-ab-run`, then run the M0.9.2 evidence intake against the experiment plan, route, benchmark and two Codex receipts.

```bash
mgsf skill-dogfood-codex <experiment.json> control <clean-control-checkout> \
  --model <exact-codex-model> --budget-seconds 900 \
  --output-root evidence/codex-ab

mgsf skill-dogfood-codex <experiment.json> treatment <clean-treatment-checkout> \
  --model <same-exact-codex-model> --budget-seconds 900 \
  --reviewed-skill <locally-reviewed-SKILL.md> \
  --expected-skill-sha256 <64-hex-SHA256> \
  --output-root evidence/codex-ab

# Once both diffs have been reviewed and committed, obtain two direct capture
# adapter eval files, and run M0.9.1 skill-ab-run.

mgsf skill-dogfood-eval <experiment.json> <skill-route.json> <benchmark.json> \
  evidence/codex-ab/<experiment-id>/control/runner.json \
  evidence/codex-ab/<experiment-id>/treatment/runner.json \
  --output-root evidence/paired-skill-dogfood
```

The Codex launcher passes the pinned, explicitly hash-approved third-party skill as *untrusted reference text* to the treatment prompt. Control receives none. It records exact model argument, budget, timestamps, command, initial baseline SHA, process return code, full prompt, stdout and stderr with byte-level SHA-256. It uses `codex exec --sandbox workspace-write` locally, does not give automatic approval to execute arbitrary referenced scripts, and does not submit, commit, push or publish.

## Intake requirements

The M0.9.2 evidence gate cross-checks plan/route hashes, exact pinned selected skill, benchmark plan hash/seed/assertion rubric, real M0.9.1 per-arm records and stdout/stderr integrity, direct capture passed in both arms, distinct committed game HEAD SHAs that differ from the baseline, a matching model/budget and valid control/treatment Codex execution receipts with unchanged logs and reviewed skill bytes.

The evaluator emits `dogfood-evidence.json`:

- `HOLD / INSUFFICIENT_SKILL_EFFECT_EVIDENCE` if anything is missing or the test only used identical game revisions.
- `REVIEW / [M0.9.1 comparative verdict]` if paired real engine evidence and provenance conditions are met. The reviewer still must confirm the tested differences are meaningful and consistent with the prompt, and inspect gameplay and visual quality.
- `promotion_status: HOLD` and `causal_claim_supported: false` **always**.

## Limits to fix before an empirical skill-effect claim

The upstream skill content SHA is a local reference hash, not remote cryptographic attestation. A runner receipt does not authenticate model/provider identity. The current M0.3b C6 screenshot capture is a *separate execution* from the Godot state test; matching HEAD binds the source revision, not the exact event timestamps. A single fixed-seed pair also cannot establish repeatability or causality. To evaluate skill effectiveness, repeat with multiple preregistered seeds/tasks and independent Codex runs, inspect direct media blind, capture execution budgets, and document unbiased human review. No fixture data should be described as live Codex work.

## Git and dependency sequence

PR #8 (M0.9) -> PR #9 (M0.9.1) -> M0.9.2. Do not merge these out of order.
