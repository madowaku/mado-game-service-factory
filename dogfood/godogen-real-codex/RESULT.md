# MGSF-M0.9.3: Real Codex Generation Dogfood Status

Date: 2026-10-15 (JST)

## Real autonomous qualification

**HOLD / NOT EXECUTED** in this milestone authoring session.

Reasons:
- The available execution sandbox did not provide Codex CLI, Godot, or
  dotnet executable. ffmpeg, ffprobe and git were available.
- A GitHub repository integration can update source, PRs and CI, but
  it does not grant an authenticated local Codex runtime.
- We did NOT ask for access tokens, copy a Codex login, or install
  credentials on public GitHub runners.
- No real Godogen/Codex-generated game was evaluated during M0.9.3 work.

## Completed

- Created a read-only Godogen source/mission/toolchain preflight.
- Added explicit double-consent, one-command qualification:
  pinned upstream intake -> Codex game loop -> separate generated C# Godot
  replay -> signed gameplay state -> decoded pixel/video correlation ->
  cross-run source/runner provenance gate.
- Added a durable qualification.json, conservative stage-level HOLD failure
  reporting, and regression tests covering missing tools, non-mutation,
  malformed pinned source, risk opt-in and synthetic positive wiring.
- Existing verified M0.9.2 engine movie/3 state checks/5 decoded pixel
  checkpoints remain independent real-engine proof, *not* AI generation proof.

## Next actual operator evidence

On an isolated, expendable, authenticated local Codex system:

1. Verify a pinned clean htdt/godogen source tree and the Godot .NET SDK/runtime.
2. Run preflight without --execute and review READY / missing_tools.
3. Run the same command with --execute --accept-generated-code-risk.
4. Confirm qualification.json and both generated-source and frame-proof
   artifacts. Inspect the resulting movie and source before promotion.
5. The first legitimate autonomous PASS must be accompanied by actual Codex
   stdout/stderr hashes and a separate engine replay, not synthetic claims.

Status: **M0.9.3 orchestration and unit contract implemented; real autonomous dogfood HOLD**.
