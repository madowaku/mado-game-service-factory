---
name: mgsf-design-to-code
description: Preserve MADO creative intent while converting authorized design references or original UI briefs into responsive working frontend code with provenance-aware browser evidence.
---

# MGSF Design-to-Code Bridge

Trigger for MGSF UI missions asking to build or repair an interface from images, Figma frames, mockups, live visual references, or a new MADO art direction.

1. Read AGENTS.md and docs/MGSF_DESIGN_TO_CODE_BRIDGE_M0_1.md in this factory.
2. Use the output of the design-to-code-plan CLI for the actual mission, instead of inventing a source of truth or copying third-party assets.
3. If upstream Atharvsinh-codez/design-to-code is explicitly installed by the operator, verify the installed source matches commit 814886518cd46afed1fcbb2377ce56dd48db4cbe and inspect its SKILL.md and conditional references. If absent, report it as unavailable, never claim execution.
4. Preserve this priority: user creative intent, authorized references/assets, established MADO identity and code conventions, then upstream skill defaults. Distinctive hand-drawn imperfections and pixel elements are allowed when the user asks for them. No universal ban on emoji, icons, or alternative fonts from third-party defaults.
5. Keep text and controls as semantic, keyboard-usable UI, not a screenshot backdrop. Test actual window interactions, responsive recomposition, focus restoration and reduced-motion behavior.
6. Use existing Astryx/Creative Intent/Shared Brain design outputs when actually present; do not invent their calls or evidence. Use Playwright and the MADO Cockpit real-UI quality gate only through available approved runtime paths.
7. Record reference and implementation screenshots, conditions, hashes, correction passes, UI behavior checks, asset rights and documented substitutions.
8. For fixture-only or self-attested results, stop at HOLD or READY_FOR_HUMAN_REVIEW. No release, paid action or publishing without independent validation and explicit authorization.

This wrapper is a local routing/policy skill. It does not contain or execute the upstream implementation skill.
