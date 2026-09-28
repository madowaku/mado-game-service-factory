# itch.io Productization Gate

Status: direct-capture proof complete; packaging gate remains

## Product shape

MADO Game Service Factory can be packaged as a game-development Tool rather than as a hosted SaaS.

The first sellable product slice should focus on one promise:

> Capture a gameplay session, preserve evidence, and produce a traceable playtest report.

Avoid selling the entire internal factory architecture as the product.

## Candidate product name

Working name: **MADO Playtest Evidence**

Internal services:

- gameplay-capture
- playtest-report
- Godot capture adapter
- real-game bridge

Customer-facing promise:

```text
record play
  -> capture screenshots/video + inputs
  -> preserve evidence
  -> generate a report tied to exact frames
```

## Paid-release gate

Technical proof completed:

- [x] direct `recorded_gameplay_capture` from a running game passes
- [x] at least one Godot project is captured end-to-end
- [x] capture-to-report finding includes direct media hashes

Still required before the first paid release:

- [ ] portable Windows package exists
- [ ] first-run command or launcher is documented
- [ ] sample project/session is included
- [ ] privacy behavior is documented
- [ ] LICENSE/EULA decision is explicit
- [ ] third-party dependency notices are reviewed
- [ ] versioned release artifact is reproducible
- [ ] support/contact route is documented

## Direct product proof

Source:

`madowaku/vertical-slice@f0514229d7f2036ec25646d09e3647c8d870dadb`

MGSF CI run:

`36488219481`

Evidence:

- two direct 1280x720 RGBA PNG captures
- SHA-256 indexed media
- direct media attached to one playtest finding
- `recorded_gameplay_capture = true`
- adapter eval PASS

This is sufficient to move productization from “concept” to “working technical slice,” but not yet sufficient for a polished paid release.

## Distribution shape

Preferred first release:

```text
MADO-Playtest-Evidence/
├── mado-playtest.exe
├── README.txt
├── examples/
├── licenses/
└── sample-evidence/
```

CLI first is acceptable for a developer tool, but a thin launcher/drop-target UI can materially improve non-engineer adoption later.

## Pricing experiment

Treat pricing as an experiment, not a permanent commitment.

Suggested phases:

1. private/free testers
2. paid early access around the low-teens USD range
3. raise price after polished packaging + second-engine or broader project proof

A higher tier can later include adapters, batch sessions, comparison reports, or team workflows.

## itch.io metadata draft

Classification: Tool

Potential tags:

- game-development
- Game Design
- Godot
- Testing
- Productivity

Only use platform flags for executables actually tested on those platforms.

## AI disclosure

The project is developed with generative-AI coding assistance.

Before publishing, review itch.io's current AI disclosure options and accurately disclose generated code and any generated text/graphics included in the distributed product.

## Product principle

Sell the outcome, not the architecture.

Bad product headline:

> Evidence-driven autonomous multi-service game development factory.

Better product headline:

> Record a playtest. Get a report that points back to the exact gameplay evidence.
