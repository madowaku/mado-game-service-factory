# playtest-report service contract

Status: **active**  
Service version: **0.1.1**  
Incubation milestone: **MGSF-M0.1**  
Promotion milestone: **MGSF-M0.2**

## Problem

MGEL preserves what a Fresh Player experienced, but raw session evidence is not yet a compact developer-facing playtest report.

## User

A game developer or coding agent that needs actionable, traceable findings from an MGEL-compatible session.

## Input

An MGEL M0 Evidence Bundle containing:

- `session.json`
- `experience_trace.jsonl`
- `friction_events.json`
- `summary.json`

The bundle may originate from the deterministic MGEL fixture or from a provenance-preserving bridge such as MGSF Real Game Dogfood Bridge.

## Output

```text
evidence/playtest-report/<fixture_id>/<session_id>/
├── manifest.json
├── report.json
├── report.md
├── eval.json
└── run.log
```

Each friction event becomes exactly one finding with severity, category, source event ID, step index, player impact, reproduction steps, expected vs actual result, recommendation, confusion/surprise evidence, and bridge policy when present.

## Severity contract

`signal = max(confusion, surprise)`

- high: signal >= 0.75
- medium: signal >= 0.40
- low: otherwise

These thresholds are deterministic service policy. They are not globally calibrated human gameplay severity.

## Promotion evidence

Deterministic fixture:

- `fixtures/playtest-report/mgel-session-001`
- one high-severity blocked-progress finding
- service eval PASS

Real-project dogfood:

- repository: `madowaku/vertical-slice`
- Godot 4.7.2 headless evidence
- source head: `7597c87bae0e66afbdb09165496843da10b0a221`
- tested PR merge: `6a2e49bd3bc20b18ccd99a825fa332380685fc4c`
- merged main commit: `9e06cdefdcad9b951fb64bae6b50873702aec03f`
- source workflow run: `33968989364`
- source job: `101314031594`
- source result: 794 tests passed, 0 failures
- C6 playfeel: 24 / 0 failures
- MGSF dogfood CI run: `36438711683`
- dogfood result: one medium-severity `near_miss` finding, PASS
- factory tests in that run: 8 passed

## Honesty boundary

Real-game bridge psychometric values are labeled:

`deterministic_model_not_human_measurement`

A bridged finding therefore means the game behavior is backed by real-project runtime evidence while confusion and surprise remain modeled values unless supplied by a future human-observation adapter.

## Active scope

Included:

- MGEL M0 ingestion
- deterministic report generation
- JSON + Markdown output
- exact friction coverage
- provenance-preserving optional bridge metadata
- deterministic eval
- real-project headless dogfood

Not yet included:

- live game control
- human telemetry ingestion
- screenshot / video evidence
- cross-session finding clustering
- calibrated cross-game severity
- hosted API or UI
