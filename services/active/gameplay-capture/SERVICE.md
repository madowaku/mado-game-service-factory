# gameplay-capture service contract

Status: **active**  
Service version: **0.3.1**  
Capture milestone: **MGSF-M0.3**  
Promotion milestone: **MGSF-M0.3b**

## Problem

Gameplay evidence must preserve not only the logical result of a play session, but also the exact media and timing that support later QA findings.

## User

A game developer or QA agent that needs screenshots/video, input timing, and traceable evidence attached to playtest findings.

## Input

A capture directory:

```text
capture.json
timeline.jsonl
media files
```

Supported evidence classes:

- `recorded_gameplay_capture`
- `reconstructed_from_verified_state`
- `synthetic_capture_fixture`

Only `recorded_gameplay_capture` is direct gameplay media.

## Output

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
- byte size
- SHA-256
- copied evidence path

Captured friction can be bridged into MGEL and then into `playtest-report`, preserving media IDs and hashes on the final finding.

## Direct Godot adapter

`mgsf godot-capture` performs:

```text
fresh Godot project checkout
  -> headless editor preflight
  -> live rendered capture scene
  -> PNG framebuffer capture
  -> capture contract
  -> media integrity index
  -> MGEL
  -> playtest-report
```

The adapter supports Xvfb on Linux CI and does not require SaaS infrastructure.

## Promotion evidence

Direct project:

- repository: `madowaku/vertical-slice`
- capture target SHA: `f0514229d7f2036ec25646d09e3647c8d870dadb`
- engine: Godot 4.7.2
- MGSF CI run: `36488219481`
- MGSF CI job: `109150207262`
- direct capture adapter: PASS
- final finding count: 1
- factory tests: 12 passed
- evidence artifact: `11000425066`

Direct frames:

- `before-swing.png`
  - 1280x720 RGBA PNG
  - SHA-256 `ac5c0ec22875fe6222021fc82d420abd3195a518904cbd39febd8ff953d7ddcd`
- `reveal.png`
  - 1280x720 RGBA PNG
  - SHA-256 `126240e5e70057d17be6322137d3c662c4361a993ce39b2cf4157a2322a98d51`

Promotion criteria verified by the adapter include:

- `recorded_gameplay_capture = true`
- `direct_media_reaches_finding = true`
- valid PNG dimensions
- source SHA preserved
- capture eval PASS
- capture-to-playtest eval PASS

## Honesty boundary

Modeled confusion and surprise remain model values unless human telemetry is supplied.

Direct PNG frames are real rendered gameplay capture from the target Godot scene. Reconstructed and synthetic fixtures remain separately labeled and cannot be substituted for direct capture evidence.
