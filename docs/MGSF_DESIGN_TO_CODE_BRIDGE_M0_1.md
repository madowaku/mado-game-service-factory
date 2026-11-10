# MGSF Design-to-Code Bridge M0.1

**Status: incubation.** This milestone adds a real mission compiler and local evidence intake. It does not claim that Codex, Playwright, or the UI have run.

## Purpose

Turn design screenshots, authorized references, or an original creative brief into a repeatable Codex UI mission without flattening MADO's design character. Integrate with existing MADO Cockpit verification as a future handoff instead of building a competing browser/visual QA system.

Upstream: https://github.com/Atharvsinh-codez/skills (MIT).
Pinned revision: 814886518cd46afed1fcbb2377ce56dd48db4cbe.

## Implemented boundary

- Validates design brief: source mode, scope, intent, authoritative references, viewports and interactions.
- Compiles a pinned and SHA-256 recorded mission pack and companion agent prompt.
- Registers a local MGSF Codex guidance skill.
- Validates submitted PNG bytes, dimensions, hashes and path containment.
- Never upgrades fixture evidence beyond HOLD.
- Even valid desktop/mobile capture claims reach READY_FOR_HUMAN_REVIEW only.

This does NOT run an agent, download external skills, run browser captures, compare reference pixels, invoke paid services, or publish/deploy anything. The origin value in the receipt is operator-supplied, not independently authenticated.

MADO Cockpit already offers a real-UI static build and Playwright evidence gate. Its current provider registry is restricted to three other design candidates. Until that is extended, do not mislabel design-to-code as one of them or claim native Cockpit receipt integration.

## Quick start

Install locally from the factory checkout:

\`\`\`sh
python -m pip install -e ".[dev]"
mgsf design-to-code-plan fixtures/design-to-code/madowaku-window-portal-001.json --output-root missions/design-to-code
\`\`\`

Output:

\`\`\`text
missions/design-to-code/madowaku-window-portal-001/
  mission.json
  AGENT_PROMPT.md
\`\`\`

This initial greenfield fixture asks for the madowaku portal with hand-drawn clickable windows. It is an original concept brief, not a licensed screenshot reference.

## Optional upstream skill installation

Inspect the upstream SKILL.md and conditional references before installation. Use the locked commit, not a moving main branch:

\`\`\`sh
git clone https://github.com/Atharvsinh-codez/skills.git <temporary-folder>
git -C <temporary-folder> checkout --detach 814886518cd46afed1fcbb2377ce56dd48db4cbe
git -C <temporary-folder> rev-parse HEAD
\`\`\`

After reviewing the instructions and license, copy only the upstream design-to-code folder to the target Codex project's .codex/skills/design-to-code/ path. The MGSF wrapper remains in this factory. The M0.1 code does not perform this download/copy automatically.

Creative intent priority: explicit user directions > authorized reference and assets > project-specific tokens/conventions > upstream defaults. In particular, upstream font and icon preferences cannot erase intentional handmade shapes, pixel art, or MADO identity.

## Evidence handoff

After a genuine operator-authorized implementation, produce a JSON receipt:

\`\`\`json
{
  "schema": "mgsf.design-to-code-render-receipt.v1",
  "mission_id": "madowaku-window-portal-001",
  "prompt_sha256": "<value from mission.json>",
  "origin": "browser_capture",
  "screenshots": [
    {"state": "desktop", "path": "screenshots/desktop.png", "sha256": "<sha256>", "width": 1440, "height": 900},
    {"state": "mobile", "path": "screenshots/mobile.png", "sha256": "<sha256>", "width": 390, "height": 844}
  ]
}
\`\`\`

The screenshot paths are relative to the existing project root and must not escape it.

\`\`\`sh
mgsf design-to-code-eval <mission-folder> <actual-receipt.json> --project-root <actual-build-folder> --output-root evidence/design-to-code
\`\`\`

The evaluation checks basic PNG integrity and provenance claims, not visual fidelity. READY_FOR_HUMAN_REVIEW does not mean Playwright was independently verified or that interaction/accessibility checks passed. Separate MADO Cockpit browser evidence, correction passes, Human Touch Lab review, and an explicit release authorization remain mandatory.

## M0.1 acceptance and M0.2 scope

- Fixture compile and tests only prove the deterministic mission/evidence contract.
- Live proof needs an authorized target worktree, reviewed skill, recorded agent/build commands, real desktop/mobile Playwright captures, reference comparisons, interaction tests, and human taste review.
- No service promotion from a fixture or a self-attested screenshot manifest.
- M0.2 should adapt the native Cockpit receipt format, support a genuine design-to-code candidate in its gated provider registry, and dogfood the actual madowaku window portal.
