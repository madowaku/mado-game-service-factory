# MGSF-M0.3 Gameplay Evidence Capture

## Goal

Preserve gameplay media and the input/result timeline as first-class, integrity-checked evidence, then carry that evidence through to actionable playtest findings.

M0.3 is deliberately split into two layers:

1. **Capture contract and evidence packager** — implemented.
2. **Engine/desktop recorder adapters** — next.

The contract is stable regardless of the recorder.

## Capture bundle

Input:

```text
capture.json
timeline.jsonl
media files
```

Output:

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

Every media artifact receives:

- stable media ID
- timestamp
- kind
- byte size
- SHA-256 digest
- copied Evidence Bundle path

## Timeline

Timeline timestamps are integer milliseconds and must be monotonic.

Typical events:

```text
observation -> input -> friction/result -> reveal
```

An event may point to a media ID, which must resolve.

Friction events carry the fields required to construct an MGEL event, including action, expected/actual result, confusion, surprise, reason, and recommendation.

## Capture to report path

```text
capture
  -> media integrity index
  -> friction event
  -> MGEL-compatible Evidence Bundle
  -> playtest-report
  -> finding
      -> media_id
      -> SHA-256
      -> copied evidence path
```

A later UI can therefore open the exact screenshot/video evidence attached to a finding without guessing which file belongs to which event.

## Evidence classes

### recorded_gameplay_capture

Direct screenshot/video produced during gameplay.

### reconstructed_from_verified_state

A visual reconstruction based on separately verified runtime state or tests.

It is useful for pipeline testing and explanation, but is not a screenshot.

### synthetic_capture_fixture

Pure fixture data used to exercise the service.

It must never be presented as game runtime evidence.

## First fixture

The first M0.3 fixture reconstructs the verified `vertical-slice` C6 one-cell-early near miss.

Its source behavior is backed by the M0.2 Godot headless evidence, but its SVG frames are explicitly reconstructed visuals.

The fixture proves:

- media hashing
- event/media traceability
- friction-to-MGEL conversion
- media-aware playtest finding generation

It does **not** prove direct framebuffer capture.

## Promotion gate

`gameplay-capture` remains incubation until at least one real `recorded_gameplay_capture` passes the same capture and capture-to-playtest evals.

The next adapter should capture real Godot, Unity, browser, or desktop media into this contract.
