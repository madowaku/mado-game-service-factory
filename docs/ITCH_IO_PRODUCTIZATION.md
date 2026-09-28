# itch.io Productization Gate

Status: draft

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
- real-game bridge

Customer-facing promise:

```text
record play
  -> capture screenshots/video + inputs
  -> detect/record friction
  -> generate evidence-backed report
```

## Paid-release gate

Do not treat the current reconstructed M0.3 fixture as a paid-product proof.

Before the first paid release:

- direct `recorded_gameplay_capture` from a running game passes
- at least one Godot project is captured end-to-end
- capture-to-report finding includes direct media hashes
- portable Windows package exists
- first-run command or launcher is documented
- sample project/session is included
- privacy behavior is documented
- LICENSE/EULA decision is explicit
- third-party dependency notices are reviewed
- versioned release artifact is reproducible
- support/contact route is documented

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
3. raise price after direct capture + polished packaging + multiple-engine proof

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
