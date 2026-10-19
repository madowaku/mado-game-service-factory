# MGSF-M1.1 Screen-only Autonomous Playtest / Evidence & Rethink Gate

## Status: incubation / promotion HOLD

This milestone introduces a bounded, dependency-injected controller/vision loop and an independent Evidence Judge contract. It is **not** a validated live autonomous Godot/Unity playtest. The public demonstration and automated tests use synthetic PNGs and a mock virtual gamepad port. A real VLM, Codex play agent, actual controller injection, Unity or Godot gameplay, and human QA have **not** been exercised in this milestone.

## Compatibility and isolation

- Base: MGSF-M1.0 Unity Official Agent Bridge draft branch. No edits to existing Godot capture APIs, EdenSpark commands, Unity probe/test, or prototype promotion decisions.
- Runtime module: src/mgsf/screen_only_playtest.py; pure Python standard library.
- Both Godot and Unity can implement the same ScreenPort interface. The port exposes only screenshot bytes and press(button,duration_ms). No game state read, scene introspection, arbitrary shell, network, compilation or editing is permitted by this module.
- A ScreenPolicy chooses a button and duration from a goal, current screenshot, bounded history and Rethink/evidence-needed signals. An IndependentJudge separately assesses before/after screenshots and the goal.
- Policy and judge identities must differ. This checks declared identity, not provider-level independence. Real use needs distinct authenticated processes/models with audit receipts.

## Live integration contract (library API, opt-in only)

    from mgsf.screen_only_playtest import run_screen_playtest
    result = run_screen_playtest(
        "fixtures/screen-only/mission.json",
        approved_screen_port, # .capture()->PNG/JPEG bytes; .press(button, duration_ms)->None
        vision_policy,        # .choose(goal, frame, history, *, rethink, evidence_needed)
        independent_judge,    # .assess(goal, before, after)->dict
        "local-evidence",
        policy_id="local-policy-provider-run-id",
        judge_id="separate-independent-reviewer-run-id",
        evidence_class="recorded_screen_port_run",
    )

The judge response is a dict with verdict PASS/FAIL/INSUFFICIENT, a nonempty reason, visible_before=True and visible_after=True. A PASS only supports **screen evidence** if the two screenshots have different content hashes; it does not prove that the intended gameplay state was reached. Judge outcomes with missing images/fields are downgraded to INSUFFICIENT. A failed judge call cannot grant PASS.

Allowed gamepad commands: A, B, X, Y, UP, DOWN, LEFT, RIGHT, START, SELECT. Each press is bounded to 30..2000 ms; max_steps 1..100; stall_threshold 2..10; rethink_budget 0..10. The mission controls a narrower button allowlist. When identical before/after screenshots reach the stall threshold, a one-shot Rethink flag is provided to the policy. A finite budget blocks infinite input loops. INSUFFICIENT sets evidence_needed for the next policy choice.

**Adapter responsibility:** run an isolated game process with explicit approval, enforce a wall-clock time limit outside this module, ensure inputs are applied, label capture provenance with engine build/commit and timestamps, and close the process on failure. The module enforces bounded steps and press durations but not a hard timeout for third-party port/policy calls. Never connect an arbitrary untrusted executable to this interface.

## Evidence and verification

Each run has a unique directory at evidence/screen-only-autonomous-playtest/<mission-id>/<run-id>:

- evaluation.json: mission goal and SHA, engine name, separate actor IDs, declared source class, screen-only assertion, supported/not-supported result and promotion HOLD
- input_evidence.jsonl: ordered gamepad presses, PNG/JPEG screenshot paths and SHA-256 hashes, changed-frame flag, independent judge verdict, Rethink triggers
- frames/: preserved input screenshots; no base64 prompts or secrets in the JSON
- manifest.json: SHA-256 and byte count for each evidence artifact

    mgsf screen-evidence-verify <evidence-directory>

The verification CLI checks hashes, path containment, sequence numbers, frame bindings, independent actor IDs and HOLD. Exit code 0 means the bundle is **internally consistent**, never that the screenshots are an authentic engine capture. This is not a signed provenance attestation and cannot establish model independence from self-reported IDs. All evidence stays local unless the operator separately uploads it.

## Gate matrix

| Observation | Result | Promotion |
| --- | --- | --- |
| Independent judge PASS, changed before/after pixels, required fields present | SCREEN_EVIDENCE_SUPPORTED | HOLD |
| Missing/invalid judgement or unchanged frame | HOLD or more observation | HOLD |
| Repeated static frames until budget consumed | STALLED | HOLD |
| Invalid action, malformed media or adapter failure | ADAPTER_FAILURE | HOLD |
| Evidence hash mismatch or path traversal | verifier FAIL | HOLD |

### Not part of this milestone

- A built-in image reasoning model, navigation memory / video-derived navgraph, model training or Skill Mining.
- Signed captures, backend identity verification, video timeline cross-checks, game-specific objective scoring or independent state assertions.
- Demonstrated autonomous real-engine gameplay. That requires separate Godot and Unity live dogfood runs, captured runtime and input receipts, independent judge provider evidence, game-specific success checks and human review. Until then, do **not** promote.

## Verification

    python -m pip install -e ".[dev]"
    pytest -q tests/test_screen_only_playtest.py tests/test_catalog.py
    mgsf validate-catalog

The contract CI job does not download Unity, install AI models, use secrets or interact with external services.
