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
- Do not claim paid-release readiness before external-user and final license/dependency review evidence exists.

## Lifecycle
candidate -> incubation -> active -> retired

A service may move backward if evidence degrades.

## Current milestone
MGSF-M0.5: QUIC Transport Probe / Network Evidence Harness — incubation

## Active services
- `playtest-report`
- `gameplay-capture`

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
