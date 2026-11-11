# MGSF Motion Graphics Bridge M0.1: Friction 1.0.0

**Status: incubation / HOLD.** Generates a Friction handoff and verifies an operator-supplied SVG animation without claiming that Friction or a browser ran.

## Rationale

The Friction 1.0.0 desktop editor supports animated SVG (SMIL), video, and image sequences, but `.friction` is currently a binary project format. M0.1 deliberately avoids reverse engineering it or relying on an undocumented CLI/plugin. Friction is free and installed separately by the operator.

Official docs: https://friction.graphics/documentation/export.html and https://friction.graphics/documentation/usage.html

## Workflow

1. **Intent**: Creative Intent Engine / Human Touch Lab decides purpose, art direction, state changes, and reduced-motion fallback.
2. **Source art**: Author or provide static, editable SVG from Inkscape or other tools.
3. **Compile**: Run `mgsf motion-graphics-plan <brief.json>` to validate dimensions, object IDs, timing and SHA-256 and output the handoff.
4. **Animate in Friction**: Import `source.svg`, preserve an editable `.friction` project and record version/export settings. Adjust keyframes and easing in the UI.
5. **Export**: For the web use animated SVG; for Godot use PNG sequence and for video use MP4/WebM. This phase does not automate image-sequence/video verification.
6. **Intake**: Run `mgsf motion-graphics-eval <mission-dir> <exported.svg>` to check SVG structure and digest. Even syntactically valid animated SVG is `READY_FOR_HUMAN_REVIEW`, not PASS.
7. **Live gate**: Verify playback, accessibility, browser/device compatibility, reduced motion, interaction reversibility, visual taste, export provenance and asset license.

## First use case: madowaku window portal

```bash
python -m pip install -e '.[dev]'
mgsf motion-graphics-plan fixtures/motion-graphics/madowaku-window-opening-001.json --output-root missions/motion-graphics
# Import missions/motion-graphics/madowaku-window-opening-001/source.svg into Friction,
# then apply keyframes in MOTION_HANDOFF.md and export animated SVG.
mgsf motion-graphics-eval missions/motion-graphics/madowaku-window-opening-001 path/to/friction-export.svg --output-root evidence/motion-graphics
```

Outputs (plan):

```text
missions/motion-graphics/madowaku-window-opening-001/
  source.svg           # static source; definitely NOT a Friction export
  MOTION_HANDOFF.md    # instructions only
  mission.json         # SHA-256 and NOT_EXECUTED
```

Output (eval): `evidence/motion-graphics/madowaku-window-opening-001-evaluation.json`.

## Contracts and guardrails

- Brief schema: `mgsf.motion-graphics-brief.v1`. Source path must stay inside the brief directory; `viewBox` must match scene resolution; tracks must target existing SVG IDs; frames must be ordered and in range.
- SVG intake rejects external references, DTD/entities, scripts, event-handler attributes, invalid viewBox and oversized SVG; it is a basic safety/integrity gate, **not** a complete SVG sanitizer. Do not serve untrusted SVG directly as active content.
- The evaluator records SHA-256, element count, declared scene and an explicitly **unverified** operator supplied origin.
- `READY_FOR_HUMAN_REVIEW` is not a successful render or browser test. Fixture evaluation never promotes the service to active.
- A web animation cannot replace the accessible DOM button and live state. Define static open/closed states and `prefers-reduced-motion` handling in the consuming app.
- Friction is GPL-3.0-only; using its separately exported assets commercially does not by itself place those assets under GPL. Review the terms for bundled source code and third-party assets independently.

## Next milestone M0.2

Capture a real Friction 1.0.0 export with the original `.friction` source, version, export configuration and media hash; run Chrome/Firefox/Safari testing with native MADO Cockpit/Playwright verification. Extend evaluation for transparent PNG sequences before claiming Godot compatibility. No automatic install, download, network or commercial dependence is required in M0.1.
