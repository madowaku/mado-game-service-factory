# playtest-report service contract

Status: **incubation**  
Milestone: **MGSF-M0.1**  
Version: **0.1.0**

## Problem

MGEL can preserve what a Fresh Player experienced, but its raw Evidence Bundle is not yet a compact developer-facing playtest report.

## User

A game developer or coding agent that needs actionable, traceable findings from a completed MGEL session.

## Input

One MGEL M0 Evidence Bundle directory containing:

- `session.json`
- `experience_trace.jsonl`
- `friction_events.json`
- `summary.json`

## Output

A deterministic service Evidence Bundle:

```text
evidence/playtest-report/<fixture_id>/<session_id>/
├── manifest.json
├── report.json
├── report.md
├── eval.json
└── run.log
```

Each friction event becomes exactly one finding with:

- severity
- source event ID
- step index
- player impact
- reproduction steps
- expected vs actual result
- recommendation
- confusion / surprise evidence

## Severity contract

`signal = max(confusion, surprise)`

- high: signal >= 0.75
- medium: signal >= 0.40
- low: otherwise

The thresholds are deterministic M0.1 policy, not a claim that they are globally calibrated gameplay severity.

## Happy path

1. Validate the MGEL bundle.
2. Cross-check event and friction counts.
3. Join friction events back to their full trace events.
4. Generate one actionable finding per friction event.
5. Write JSON and Markdown reports.
6. Evaluate traceability and actionability.
7. Write the service Evidence Bundle.

## Failure modes

The service fails closed when:

- any required MGEL file is absent;
- JSON / JSONL is invalid;
- fixture or session identity disagrees across files;
- summary counts disagree with evidence;
- a friction event cannot be traced to an experience event;
- trace event IDs are missing or duplicated.

## Evidence

M0.1 uses a committed deterministic fixture reconstructed from the public MGEL M0 contract. Real-project dogfood remains required before promotion from incubation to active.

## Eval

The eval passes only when:

- source identity is preserved;
- friction coverage is exact;
- every finding traces to an event;
- every finding has actionable reproduction and recommendation fields;
- every severity value obeys the service contract.

## MVP boundary

Included:

- MGEL M0 ingestion
- deterministic report generation
- Markdown + JSON output
- service Evidence Bundle
- deterministic eval

Not included:

- live game control
- LLM interpretation
- screenshots / video
- clustering duplicate findings across sessions
- calibrated cross-game severity
- hosted API or UI
