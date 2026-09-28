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

## Required artifacts for a promoted service
- service spec
- runnable implementation
- deterministic fixture
- eval definition
- Evidence Bundle
- real-project dogfood
- catalog entry with lifecycle stage

## Lifecycle
candidate -> incubation -> active -> retired

A service may move backward if evidence degrades.

## Current milestone
MGSF-M0.2: Real Game Dogfood Bridge — complete

## Mission 001 status
Mission 001 has produced its first active service: `playtest-report`.

Its promotion is backed by both deterministic fixture evidence and `madowaku/vertical-slice` real-project Godot headless evidence.

## Next boundary
MGSF-M0.3 should increase evidence fidelity rather than add SaaS surface area. Prefer a live/recorded gameplay capture adapter, screenshot/video evidence, or human-observation ingestion over auth, billing, or hosted UI.
