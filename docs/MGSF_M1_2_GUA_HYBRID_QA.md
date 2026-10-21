# MGSF-M1.2 Gua Semantic Game QA Bridge / Hybrid Visual Proof

**Status: incubation. Promotion: HOLD.** Opt-in native desktop Gua MCP integration with a synthetic mock contract test. This stage does not prove an autonomous real Godot or Unity playtest. Existing M1.1 screen-only behavior is unchanged.

## Two complementary observation channels

M1.1's screen-only agent sees images and virtual gamepad history but not engine state. M1.2 reads Gua Semantic UI/World trees and Gua screenshots, then performs one allowlisted UI click. The host-side action completion, semantic postcondition, and changed image hashes are three separate checks. They are not an independent vision judge. UI/World/screenshot reads are not atomic.

The goal is to detect cases such as a scene reporting that a button worked while the rendered display did not change. This module does not assert that semantic correctness implies visual quality.

## Compatibility and security

- Upstream: https://github.com/gua-project/gua (MIT). Pin and review an actual upstream release before real integration. Avoid using a floating latest in a production workflow.
- Upstream support at design time: Godot 4.7 GDScript addon and Unity 6000.5+ desktop Mono. No IL2CPP or mobile support assumed.
- Gua must already be enabled inside a running isolated test game. An installed gui-mcp executable must be available; MGSF does not download Gua, start games, modify game projects, install Bun, or change exposure policies.
- One explicit --execute is required for the only action, click_node. The bridge address must be local: ws://127.0.0.1:PORT or ws://localhost:PORT.
- The allowlisted MCP calls are get_ui_tree, get_world_object_tree, get_screenshot, click_node. Arbitrary shell, raw input, logs, and private state reads are not offered by this bridge.
- Screenshots are generally forbidden in Gua Player exposure mode, and should remain so for shipped games. Only opt in on an approved local Debug/test host. An unauthorized screenshot must fail the probe.
- The operator-selected --mcp-executable must be trusted and pinned before use. Mission data cannot select a program.
- Never run against networked multiplayer, valuable saves, or untrusted binaries. The allowed click still has a real in-game effect.

## Live setup example (not yet exercised)

1. Create an isolated Godot 4.7 project with the matching Gua addon / GDExtension, enable its local debug bridge and run the game.
2. Install a reviewed/pinned upstream gui-mcp executable. Verify that it can connect to the local Gua bridge.
3. Inspect actual node IDs through the Gua Inspector. Replace the following placeholders with stable IDs from that game.
4. Prepare a mission:

       {
         "schema_version": 1,
         "mission_id": "title-to-gameplay",
         "engine": "godot",
         "action": {"tool": "click_node", "nodeId": "Start"},
         "expected_after": {
           "tree": "ui", "id": "Gameplay",
           "field": "visible", "equals": true
         }
       }

World objects must be explicitly registered in Gua. For an optional world assertion, expected_after may instead be:

       {"tree":"world","id":"checkpoint","field":"state.reached","equals":true}

Predicate fields are visible/enabled/label/role/kind/active or one state.<primitive-field>. No arbitrary code or query execution.

5. Run an explicitly authorized in-game click:

       mgsf gua-probe fixtures/gua/mission.json --execute --mcp-executable gui-mcp --bridge-url ws://127.0.0.1:8765 --output-root evidence

6. Verify the evidence directory:

       mgsf gua-verify evidence/gua-hybrid-semantic-proof/<mission-id>/<run-id>

An integrity PASS is not an engine-authenticity proof.

## Artifact contract

Unique run directory includes:

- mission.json and before_ui.json / after_ui.json / before_world.json / after_world.json
- before.png and after.png (Gua get_screenshot PNG bytes)
- action_receipt.json with request/host completion data
- assessment.json with completion, same-session, semantic and image-change checks
- evaluation.json with explicit source class, unsupported runtime provenance, promotion HOLD
- manifest.json containing SHA-256 and file lengths for all other artifacts

The verifier checks hashes, required files, mission postcondition, receipt assessment and frame change. It is not a signed attestation; malicious rewrites of both files and manifest could still evade it. Real runtime provenance and model independence remain unverified.

## Decision table

| Observation | Result | Promotion |
| --- | --- | --- |
| Host-completed click, same Gua UI session, expected state, different screenshots | HYBRID_EVIDENCE_SUPPORTED | HOLD |
| Same conditions, but screenshots unchanged | SEMANTIC_EVIDENCE_ONLY | HOLD |
| Missing host completion, changed session, missing postcondition | HOLD | HOLD |
| Denied screenshot, malformed tool data or adapter exception | ADAPTER_FAILURE | HOLD |
| Missing or corrupted artifact, extra file | verifier FAIL | HOLD |

A read-only semantic snapshot cannot prove the absence of unregistered world objects. Action completion is not a guarantee that a higher-level gameplay goal was achieved. No unconfirmed action is automatically retried.

## Synthetic contract dogfood, not real game evidence

    python -m pip install -e ".[dev]"
    pytest -q tests/test_gua_semantic_bridge.py tests/test_screen_only_playtest.py tests/test_catalog.py
    python scripts/demo_gua_contract.py --output-root evidence/gua-mock
    mgsf validate-catalog

The deterministic demo produces *synthetic* one-pixel PNG images and mock MCP responses, not real gameplay captures or VLM decisions. It writes an auditable HOLD evidence bundle to CI.

## Next live proof gates

1. Lock Gua addon, MCP package and Godot versions; validate local Windows/Godot installation.
2. Collect actual engine process/commit/build, Gua version, timeline, runner return codes, capture provenance, and logs. Verify against the real process instead of self-reported strings.
3. Run one actual Godot scene action and confirm native Gua host completion, semantic post-state and direct PNGs.
4. Compare the same mission and action budget via M1.1 screen-only and M1.2 hybrid. Report measured completion, false positives, elapsed time, token usage and failures. Never invent fixture-based performance benefits.
5. Expand to Unity Mono only after real Godot proof. Keep privileged Debug data separate from release agent exposure. Human review required before promotion.

This branch intentionally builds on M1.1, which itself builds on M1.0. Existing Godot capture, Unity adapter, screen-only loop and promotion rules remain untouched.
