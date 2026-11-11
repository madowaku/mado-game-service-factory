---
name: mgsf-motion-graphics
description: Compile reusable Friction motion briefs, guide editable SVG animation handoff, and review exported SVG evidence without inventing engine or browser proof.
---

# MGSF Motion Graphics Bridge

Use for UI titles, window opening, result animations, logos and game motion assets when a separate editor adds value. Prefer existing project motion conventions and simple CSS when a Friction project is unnecessary.

1. Inspect user creative intent and existing motion components. Preserve Human Touch Lab texture and handmade asymmetry when intentional.
2. Put static SVG (named groups) and brief JSON together in `fixtures/motion-graphics/`; run `mgsf motion-graphics-plan ...`.
3. Open generated `source.svg` in **Friction 1.0.0**, animate by hand and retain the native `.friction` file. Do not claim the compiler created/edited a Friction document.
4. For web, export animated SVG; inspect differences from Friction's viewport. For Godot, use transparent PNG sequence; for video use MP4/WebM.
5. Run `mgsf motion-graphics-eval <mission> <exported.svg>` for web SVG only. It verifies basic SVG structure and hashes, not source identity or true rendering.
6. Require real app playback, reduced-motion, keyboard/accessibility, interruption, and aesthetic review before release. Synthetic samples or self-attested provenance remain HOLD or READY_FOR_HUMAN_REVIEW, never active evidence.

Do not automatically install third-party binaries or copy GPL code into the product. Friction runs as a separate desktop editor.
