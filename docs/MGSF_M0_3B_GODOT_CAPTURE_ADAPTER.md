# MGSF-M0.3b Godot Capture Adapter

Status: **COMPLETE**

## Goal

Produce a real `recorded_gameplay_capture` from a running Godot project and carry that media through to a traceable playtest finding.

## Architecture

```text
Godot project
  -> editor preflight
  -> capture scene
  -> rendered framebuffer
  -> PNG frames
  -> capture.json + timeline.jsonl
  -> gameplay-capture
  -> MGEL
  -> playtest-report
  -> finding with media hashes
```

## First target

Repository:

`madowaku/vertical-slice`

Capture target:

`f0514229d7f2036ec25646d09e3647c8d870dadb`

Scenario:

C6 one-cell-early SWING near miss.

The capture runner replays the verified route, captures a frame before SWING, performs the miss, enters REVEAL, and captures the reveal frame.

## Why the preflight exists

A fresh Godot checkout may not yet contain the generated global script-class cache.

The adapter first runs:

```text
godot --headless --editor --path <project> --quit-after 1
```

Then it launches the direct capture scene with a real display, using Xvfb on Linux CI.

This keeps the adapter usable on clean checkouts instead of depending on editor state left by a developer machine.

## Evidence

MGSF CI run:

`36488219481`

Job:

`109150207262`

Result:

```text
adapter=godot-capture findings=1 eval=PASS
12 passed in 0.09s
```

Adapter criteria included:

```text
recorded_gameplay_capture = true
direct_media_reaches_finding = true
status = PASS
```

Direct frame evidence:

```text
before-swing.png
1280 x 720 RGBA
sha256 ac5c0ec22875fe6222021fc82d420abd3195a518904cbd39febd8ff953d7ddcd

reveal.png
1280 x 720 RGBA
sha256 126240e5e70057d17be6322137d3c662c4361a993ce39b2cf4157a2322a98d51
```

Evidence artifact:

`11000425066`

The artifact contains the raw Godot capture, adapter eval, gameplay-capture Evidence Bundle, MGEL bridge, and playtest report.

## Lifecycle result

```text
gameplay-capture
candidate
  -> incubation
  -> reconstructed fixture PASS
  -> direct Godot capture PASS
  -> active
```

## Product significance

The tool no longer demonstrates only a reporting pipeline.

It now demonstrates the customer-visible loop:

```text
run game
  -> capture what happened
  -> preserve exact evidence
  -> generate a finding tied to that evidence
```

That is the first technically credible slice of the proposed itch.io product.
