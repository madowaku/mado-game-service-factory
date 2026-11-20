# MGSF Launch Cinema M0.1

**Status: incubation / planning implemented.** No Ava authentication, external plugin installation, product-page capture, paid call, video render or real-world QA has been executed by this milestone.

## Purpose

Translate a MADO game's launch idea into a repeatable, traceable Codex handoff for a short 9–15 s opening. The first experiment is **madowaku: a window opens**. Reuse Motion Foundry concepts where possible, while leaving all video rendering inside an operator-controlled local environment.

Upstream: https://github.com/hologramxyz/avastudio-mcp

Reviewed repository revision (2026-11-17): `272410c0a42318b3a0cd85e025e8ed5856637b04`. Inspect it and its script dependencies again before any use. The upstream `launch-remake` skill is **not vendored** or automatically installed.

Official feature reference: https://avastudio.com/tools/launch-videos

## Implemented now

- A schema-validated, offline `mgsf launch-cinema-plan` command.
- A deterministic `mission.json` with brief SHA-256, pinned upstream revision, `NOT_EXECUTED`, `HOLD` and `release_approved: false`.
- A local `AGENT_PROMPT.md` for a later reviewed agent run.
- A project-local routing skill, a madowaku teaser fixture and a manual evidence/evaluation contract.

There is **no** integrated Ava API, sound generator, rendering engine, receipt evaluator or automatic installer in M0.1.

## Quick start (free, offline)

```sh
python -m pip install -e ".[dev]"
mgsf launch-cinema-plan fixtures/launch-cinema/madowaku-window-teaser-001.json \
  --output-root missions/launch-cinema
```

Expected output:

```text
missions/launch-cinema/madowaku-window-teaser-001/
  mission.json
  AGENT_PROMPT.md
```

A missing `product_url` is deliberately recorded as **UNCONFIRMED**. Confirm a running page controlled by the project before any capture. The repo name alone is not a verified product URL.

## Optional local Ava handoff

Ava's official instructions for Codex:

```sh
codex plugin marketplace add hologramxyz/avastudio-mcp
codex plugin add avastudio@avastudio
```

Use them **only on an operator-controlled Mac/Linux computer after reviewing the plugin and dependencies**. Sign in with Ava manually. Search requires less access than music generation; prefer the minimum scopes needed. A hosted ChatGPT MCP connection can browse launch references, but local video production also requires a shell/filesystem, Chrome, FFmpeg and HyperFrames. The upstream skill can run setup scripts, so inspect these rather than accepting an unattended installation.

Reference search can be free. Ava's launch-music step can consume credits, so the sample brief sets `ava_credit_limit: 0` and requires a separate explicit approval before any paid call. Using third-party audio as a style reference also needs clearance.

## Creative and rights policy

1. Capture real owned project screens and actual product behavior; no generated stand-in UI, imaginary numbers or invented achievements.
2. Search 3–5 references, evaluate fit, and record creator, title, original URL and license/permissions. Viral success is not a reuse license.
3. Borrow high-level pacing and camera vocabulary while developing an original sequence. Do not republish/reference-match protected footage, music, people, logos, narration or distinctive creative expression without rights.
4. First create the 9–15 s opening. Prioritize a real madowaku window interaction, an intelligible story and a legible CTA. Keep reduced-motion needs in mind for embedded web presentation.
5. For an authorized local experiment, follow the upstream `launch-remake` skill's diagnostics and quality checks. Preserve actual command output from `check.cjs` and `compare.py` plus story-read results. Do not assume they passed.
6. Never publish, automatically upload private files, commit rendered assets or start paid calls without explicit approval.

## Evidence bundle for a future live run

Required records:

- **Input:** mission and brief SHA-256, confirmed product page or local dev-server origin, captured source commit, screenshot/capture hashes and a rights register for every external asset.
- **Reference:** original creator, post URL, selected aspect ratio, permission findings and a human-reviewed story/shot map.
- **Execution:** upstream revision, tool versions, local invocation log, auth-scope note without secrets, charged credits (if any), captured UI and native HyperFrames project.
- **Output:** MP4 file, duration, dimensions, frame count, SHA-256 checksum, sound provenance and reference credit.
- **QA:** actual upstream checks, independent playback and readability review, narrative/factual accuracy, third-party-rights review and final human verdict.

A deterministic fixture is always `HOLD`. The presence of a video file or agent's claim of successful rendering does not prove QA or authorize publication. There is no automatic promotion gate for this service in M0.1.

## Acceptance / next milestone

M0.1 succeeds if the brief compiles deterministically and tests establish that unsafe identifiers, invalid durations, publication pre-approval and invalid credit limits are rejected. This does **not** count as live video dogfood.

M0.2 requires one real local Codex + Ava run, all media and runner evidence, independent review of the output and an explicit user publication decision before claiming a usable production workflow.
