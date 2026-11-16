# MGSF Sakuga Interaction Layer M0.1

**Status: incubation / offline proof of integration.** No production Cockpit UI, Godot game, agent worker or release pipeline has been modified. No real build or QA operation is performed by the demo.

## Goal

Study expressive *sakuga* interaction feedback in a local browser with minimal dependencies, while keeping the state transition truthful. MGSF collects the proven interaction recipe; Human Touch Lab evaluates feel; MADO Cockpit remains the owner of real control-plane actions.

Upstream: https://github.com/finktheartist/sakuga-vfx
Pinned upstream commit: `c3dabb173928a3ad2372183103caf2e6f50953d0`
License: MIT, copyright 2026 Justin Finkelman. Retained in `services/incubation/sakuga-interaction/vendor/LICENSE`.

## Delivered in M0.1

- Vendored, unmodified `button.js`, `checkbox.js`, `progress.js` from the pinned revision. Each is self-contained and shares the global SakugaFX core after first load.
- Original local demo `services/incubation/sakuga-interaction/index.html` with the correct public APIs: button `done()`, checkbox `change` and `checked`, progress `set(fraction)`, `reset()` and `sakuga:done`.
- A deterministic **simulated** 8-step operation, intentionally never presented as successful product QA, engine build or release evidence.
- Byte-integrity tests for every upstream file and an offline-boundary check.
- No new runtime dependencies, API key, paid service, network asset, CDN, Node package or build tool. The checkbox replaces the 500 KB animated toggle during M0.1 to keep the proof small.

## Try locally

From the repository root:

```sh
python -m http.server 8000 --bind 127.0.0.1 --directory services/incubation/sakuga-interaction
```

Visit `http://127.0.0.1:8000`, press **Run simulation**, observe completion, change **Require human review**, then press **Reset**.

The test command is:

```sh
python -m pytest tests/test_sakuga_interaction.py -q
```

## Integration contract for a future Cockpit adapter

1. Use the real control-plane data and present numeric progress only when evidence actually supports a number. No `demo` attribute in production.
2. Call `button.done()` only on an authoritative successful result, not when clicked or when an optimistic frontend request returns.
3. Keep server authorization and the existing Human Question Gate unchanged; the visual response never grants a new power.
4. Reserve static UI space around burst effects. The global canvas may paint above overlays and burst back-layers may be clipped by `overflow:hidden`.
5. Preserve keyboard, screen-reader and reduced-motion behavior. Provide a visible status text and distinct error/reset states; do not rely on the animation to communicate meaning.
6. Keep the web-component bridge isolated from React/Python/Godot runtime state. Godot does not natively consume these browser custom elements; it would need an explicit separate adapter.
7. Prefer sparse impact at completion and soft feedback for routine operations. Avoid perpetual motion or surprise animation in mission control.

## Evidence and promotion gate

Current evidence: pinned source and programmatic integrity checks plus a self-contained offline *simulation*. These prove only source provenance and demo wiring, not rendered visual quality.

**Unverified:** real browser execution, touch and keyboard paths, responsive overflow, frame-by-frame quality, Safari/Firefox, screen-reader behavior, GPU/battery cost, modal layering, and real Cockpit integration. There is no independent Playwright screenshot or human taste approval.

Before promoting beyond incubation:
- Capture desktop 1440px and mobile 390px states from a real browser, including mid-animation and reduced motion, with reproducible test commands.
- Verify pointer/touch, keyboard, forms, focus, status announcements and 200%-zoom readability.
- Test two failure cases: genuine backend failure (no completion mark) and reset during animation (no stale completion).
- Run in the actual Cockpit UI under its CSP and policy gates with a kill-switch; check overlays and no sideways scroll.
- Have Human Touch Lab review the sequence (anticipation, impact, follow-through, settle) and its restraint.
- Confirm all third-party licensing and evidence receipts before production release.

The promotion gate is HOLD until those conditions are demonstrated with artifacts. Never treat a passing fixture or an AI claim as real-world QA.
