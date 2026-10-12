# MGSF-M0.9 AI Game Verification Protocol v0.1

## Purpose

Catch specification omissions and gameplay-state errors that can survive unit tests or screenshot review. This is a NEW milestone, not a replacement for the existing M0.8 EdenSpark prototype-promotion gate.

## Contract

- Input: a YAML game specification (schema v1), a JSON action/state/event replay (schema v1).
- Requirements declare `id`, `description`, `critical`, bounded `actions`, and `assertions`.
- Assertions support state `path` + `equals`, `same_as_before`, or event occurrence `event` + `count`. `at_step` is zero-based.
- Every declared requirement must have exactly one case. Undeclared or duplicate cases are errors.
- Replay actions must match **in exact order**. Missing state paths fail closed.
- Reports preserve exact input copies, SHA-256 digests, per-assertion explanations, coverage, and failed requirement IDs.

## Run

```bash
mgsf verify-game fixtures/verification/hp-game-over.yaml \
  fixtures/verification/hp-game-over-trace.json \
  --output-root evidence/ai-game-verification
pytest -q tests/test_game_verification.py
```

Expected evaluation: `verification_status=PASS`, `release_gate=HOLD` for the known-good deterministic fixture.

## Critical evidence boundary

v0.1 deliberately accepts **only** `deterministic_game_fixture`. It verifies a data contract; it **does not execute Godot** and cannot establish trace authenticity. An agent-authored trace, video, or self-reported `recorded_godot_execution` is not engine evidence. Passing tests **must remain HOLD**, and failed assertions **FAIL**. Human experience ratings are not modeled as real user tests.

Before the gate can PROMOTE, future M0.9.1+ must add a trusted runner that launches Godot and captures actual input and post-action state with timing, source revision, engine logs, process exit code, and hashed artifacts. Then add independent human playtest provenance and a human approval step. The existing gameplay capture adapter is for direct media; media alone must not be treated as state-trace attestation.

## Repair loop

Failed assertion `check` and `reason` fields are actionable Codex feedback. Automatic changes remain out of v0.1. No games are published, uploaded, or submitted.
