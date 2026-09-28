# gameplay-capture service contract

Status: **incubation**  
Milestone: **MGSF-M0.3**  
Version: **0.3.1**

## Problem

MGSF-M0.2 can consume real-project headless test evidence, but it cannot yet preserve the visual/media layer of an observed gameplay session.

## User

A game developer or QA agent that needs screenshots, videos, and input/result timing to remain attached to later playtest findings.

## Input

A capture directory:

```text
capture.json
timeline.jsonl
media/
  frame or video files
```

`capture.json` declares:

- capture ID and session ID
- source provenance
- evidence class
- media IDs, paths, kinds, and timestamps

`timeline.jsonl` declares timestamped events such as:

- observation
- input
- result
- friction
- marker

Events may reference a media ID.

A friction event must also provide:

- action
- expected result
- actual result
- confusion
- surprise
- reason
- recommendation

## Evidence classes

- `recorded_gameplay_capture`: direct screenshot/video produced during gameplay.
- `reconstructed_from_verified_state`: visual reconstruction based on separately verified project state.
- `synthetic_capture_fixture`: deterministic fixture used only to test the capture pipeline.

These classes must not be presented as interchangeable.

## Capture output

```text
evidence/gameplay-capture/<capture_id>/<session_id>/
├── manifest.json
├── media_index.json
├── timeline.jsonl
├── eval.json
├── capture_playtest_eval.json
├── mgel/
└── media/
```

The service copies media into the Evidence Bundle and records SHA-256 and byte size for each item.

## Capture to playtest

`mgsf capture-playtest-report <capture-dir>` performs:

```text
capture media + timeline
  -> integrity index
  -> captured friction
  -> MGEL-compatible event
  -> playtest-report
  -> finding with media IDs + SHA-256
```

This lets a finding point back to the exact media artifacts used as evidence.

## M0.3 eval

PASS requires:

- at least one media artifact;
- non-empty SHA-256 indexed media;
- a monotonic timeline;
- at least one input event;
- at least one observable result/observation/friction event;
- all timeline media references resolve;
- evidence class is explicit;
- captured friction can reach a playtest finding with media hashes intact.

## Honesty boundary

A reconstructed frame is not a screenshot.

A synthetic frame is not a gameplay capture.

Only `recorded_gameplay_capture` may be described as direct gameplay media.

## Current boundary

The capture contract and capture-to-report path are implemented.

The service remains incubation because the committed fixture uses `reconstructed_from_verified_state`, not a direct framebuffer capture.

A later recorder adapter may generate direct screenshots/video from Godot, Unity, browser, or desktop capture without changing the service contract.
