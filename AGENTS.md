# AGENTS.md

## Mission
Build small, evidence-backed services that remove friction from game development.

The factory must prefer working, testable services over speculative infrastructure.

## Operating loop
1. DISCOVER recurring game-development friction.
2. SELECT candidates that are frequent, automatable, dogfoodable, reusable, and small enough for an MVP.
3. SPEC the problem, user, input, output, happy path, failure modes, evidence, eval, and MVP boundary.
4. BUILD the smallest useful CLI or local tool first.
5. DOGFOOD on both a deterministic fixture and a real project when available.
6. EVAL with explicit pass/fail criteria.
7. SHIP only if evidence exists and the eval passes.
8. OBSERVE outcomes and either IMPROVE or RETIRE.

## Non-negotiable rules
- Do not start with SaaS UI, auth, billing, Kubernetes, or speculative platform infrastructure.
- Do not mark a service successful from a fixture alone.
- Do not promote a service to active without an Evidence Bundle.
- Prefer small reversible changes.
- Reuse existing MADO capabilities when practical instead of rebuilding them.
- Keep service-specific code isolated from factory orchestration.
- Every service must have a machine-readable catalog entry.
- Never describe modeled experience values as human measurements.
- Never describe reconstructed or synthetic media as a direct gameplay capture.
- For direct media, preserve source SHA, media hash, dimensions, and capture provenance.
- Do not treat an AI agent claim as proof of an engine action without runner and artifact evidence.
- Do not publish or submit games from autonomous dogfood loops.
- Do not claim paid-release readiness before external-user and final license/dependency review evidence exists.

## Lifecycle
candidate -> incubation -> active -> retired

A service may move backward if evidence degrades.

## Current milestones
- MGSF-M0.5: QUIC Transport Probe / Network Evidence Harness - incubation
- MGSF-M0.6 to M0.8: EdenSpark Agent-Native Prototype Loop - incubation

## Active services
- `playtest-report`
- `gameplay-capture`

## Incubation services
- `quic-transport-probe`
- `edenspark-agent-adapter`
- `edenspark-autonomous-playtest`
- `prototype-promotion-gate`

## Product preview
`MADO Playtest Evidence 0.4.0` builds as a single-file Windows x64 executable and is distributed with an offline sample, privacy statement, preview license, third-party notices, support instructions, sample report, and per-file release hashes.

Windows verification:

- run `36493989574`
- job `109169128163`
- 15 tests passed
- bundled demo PASS
- sample analyze PASS
- versioned ZIP uploaded as artifact `11001819146`

## MGSF-M0.5 boundary
Build the smallest network evidence harness before choosing a QUIC runtime.

Prioritize:
- packets/sec and bytes/sec
- RTT p50/p95 and jitter
- loss/disconnect evidence
- explicit fixture vs live provenance
- HOLD promotion gate until live network evidence exists

Do not call reconstructed SEGA slide values a live network measurement.

## Deferred boundary
External Tester Preview remains important and moves to the next unallocated milestone after M0.5.


## EdenSpark boundary
MGSF must not reimplement EdenSpark's MCP transport. The project-provided MCP configuration is consumed by Codex. MGSF owns the mission, retry budget, runner evidence, artifact hashing, and promotion decision.

A deterministic EdenSpark fixture is useful only for contract regression and must remain HOLD. Prototype promotion requires a real recorded `codex-exec` run with all required actions, no reported runtime errors, a successful runner return code, and at least one preserved artifact.


## MGSF-M1.0 Unity boundary

Keep Godot service commands and evidence unchanged. The Unity adapter is incubation and opt-in; do not silently install the Unity official plugin, Unity CLI, Editor or Pipeline package. Never copy Unity Companion License upstream skills without explicit license review. Do not perform arbitrary C# eval, deploy, monetize, or publish. Unity CLI test PASS / Editor READY is not gameplay proof and may not promote this adapter. Real gameplay, progressing frames, inputs, screenshots and console evidence remain required.

## MGSF-M1.1 screen-only QA boundary

Keep game controller/capture ports and policy/judge model adapters separate. The core screen-only loop may observe PNG/JPEG bytes and issue allowlisted, bounded gamepad presses only. Never infer game success from agent prose, unchanged screenshots or synthetic fixtures. Store each input and screenshot SHA-256 with a verification manifest, trigger finite Rethink on repeated unchanged frames, request extra evidence on INSUFFICIENT, and maintain promotion HOLD until real independently validated Godot/Unity runtime receipts and human review exist. Do not turn a local bundle's internal hash consistency into an authenticity claim.
