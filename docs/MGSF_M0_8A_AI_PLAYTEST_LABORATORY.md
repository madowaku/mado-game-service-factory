# MGSF-M0.8a: AI Playtest Laboratory / Autonomous Gameplay Refinement

## Compatibility

The existing MGSF-M0.8 is **Prototype Promotion Gate**. This `M0.8a` track is an additive Godot replay and scoring service; it does not replace `prototype-promote`, the EdenSpark runner, `gameplay-capture`, or `playtest-report`.

## Why this is useful

Game correctness and human enjoyment are different propositions. The laboratory provides reproducible measurements of *observable state*: goal reached, stalled progress, deaths, retries, runtime errors and total input frames. It deliberately does **not** produce a made-up "fun score." Its `persona` describes a test cohort; the first implementation uses reproducible scripted actions or an externally agent-authored plan, not self-directed in-game AI.

## Scenario v1

A JSON scenario contains `scenario_id`, Godot `scene`, scene-relative `state_node`, `steps` (`action` + `frames`), and `limits` (`max_stalls`, `max_deaths`, `max_retries`). The target game must implement `mgsf_playtest_state() -> Dictionary` on the observed node, returning:

```gdscript
func mgsf_playtest_state() -> Dictionary:
    return {
        "progress": progress_counter,
        "won": is_level_complete,
        "deaths": death_count,
        "retries": retry_count,
    }
```

`progress` should be monotonic while the player advances. Deaths and retries are nondecreasing cumulative counters. Missing state, actions, or trace rows fail closed. The Godot replay uses `InputEventAction` and `process_frame` to exercise the real scene, with no fabricated inputs in the evidence file.

## Commands

```bash
# From an editable checkout: pip install -e '.[dev]'
mgsf playtest-lab-godot fixtures/playtest-lab/godot-smoke fixtures/playtest-lab/godot-smoke/scenario.json \
  --godot /path/to/godot --persona qa --output-root evidence
mgsf playtest-lab-eval evidence/playtest-lab/<session-id>
mgsf playtest-lab-brief evidence/playtest-lab/<session-id> --output-root evidence/refinement
# After a reviewed, reversible game change and a second run:
mgsf playtest-lab-compare <before-session-dir> <after-session-dir> --output-root evidence/refinement
```

The `brief` command produces a Codex-ready prompt for one reversible improvement and asks for a replay/compare cycle. It does not execute Codex, publish a game, merge code, or pretend that a prompt alone is an autonomous correction loop.

## Evidence and promotion policy

- `deterministic_playtest_fixture` has status `HOLD`, even with perfect metrics.
- `recorded_godot_playtest` requires a successful Godot runner, sentinel, hashes for scenario/trace/stdout/stderr, and a 40-character project source commit hash. Success is `PASS` only when every state criterion passes.
- The comparison requires exactly the same scenario bytes, persona, and driver. `IMPROVED` requires a verified live baseline and after run, after status `PASS`, at least one improved observable metric, and **no** metric regression. `REGRESSION`, `ITERATE`, `UNCHANGED`, and `HOLD` prohibit automatic promotion.
- The evidence is local process attestation, not cryptographically tamper-proof remote verification. A malicious user could fabricate all local files. Consumers should preserve bundles in trusted CI and require a human review before merging.
- Status `IMPROVED` is *not* equivalent to the factory's cross-engine `PROMOTE` gate. It is only a measured refinement candidate.

## Next iterations

1. Add a driver protocol that lets Codex/other AI choose actions from the Godot state observation step by step, with strict action/time budgets.
2. Add curated novice/expert/chaos cohorts and multiple seeded runs, publishing per-cohort distributions instead of a single run.
3. Connect direct `gameplay-capture` frame hashes and human rating samples, so evaluator state and perceived enjoyment are considered separately.
4. Add a gated Codex patch runner using the existing EdenSpark retry pattern and opt-in human-controlled merge permissions.

For now the live integration smoke scenario is a simple instrumented Godot scene. It proves the plumbing, **not** quality on a real third-party game. Real project dogfood remains a promotion prerequisite.
