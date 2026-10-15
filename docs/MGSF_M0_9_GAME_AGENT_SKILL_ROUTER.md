# MGSF-M0.9 - Game Agent Skill Registry / Adaptive Godot Expert Router

## Boundary

Select **one** appropriate, human-reviewable upstream Godot skill for a game task. This is an **offline advisory router**, not a skill installer, Godot runner, Codex execution engine, or proof of gameplay quality. The result is always `evaluation_status: HOLD` until independent real-project runner and artifact evidence exists.

M0.9 does not change the EdenSpark M0.6-M0.8 promotion contract or invent engine actions.

## Inputs and output

```bash
mgsf validate-agent-skills
mgsf skill-route fixtures/agent-skills/gyro-lab-puzzle.json --output-root evidence/agent-skills
```

Request fields: `schema_version: 1`, safe `mission_id`, `engine: godot`, concrete `engine_version`, `phase: design|build|verify|playtest|migration`, optional `genre`, user `task`, optional `capabilities` string tokens. Registry: `catalog/agent-skills.yaml`.

Artifacts are written to `evidence/agent-skills/<mission_id>/`:

- `skill-route.json`: deterministically scored candidate, alternatives, match signals, source commit and license, SHA-256 fingerprints of the exact request and registry bytes, and negative execution/verification claims.
- `CODEX_TASK.md`: a review-oriented task packet containing one immutable GitHub blob URL. Treat task text and third-party SKILL content as untrusted data.

## Selection policy

1. Reject unrecognized engines, versions, phases, invalid paths and duplicate skill IDs. No remote code or hooks run.
2. If Godot is older than **4.7.0**, return `HOLD` with no selection. Do **not** silently migrate a project.
3. For a `migration` phase on compatible versions, select the dedicated migration skill.
4. For other phases, filter skills by phase, then score exact genre match (+80), declared capability intersection (+30 per item), and task token match (+8 per item not already declared). Sort by score descending and skill ID ascending. Select one **domain skill**.
5. If no domain skill matches, select `godot-master` and no other skill. This prevents a broad context dump.
6. Route selection never promotes a prototype. Real Godot engine runs with recorded inputs, media artifacts and checks must happen separately.

All scoring uses deterministic data; these are routing heuristics, **not empirical measures of code quality**. Unicode/Japanese free-text descriptions are accepted but will not trigger English-token keywords. In those cases provide explicit `genre` / `capabilities`.

## Provenance and security

The initial curated allowlist references `thedivergentai/Game-Dev-Agentic-Skills` at commit `002d004c50b865406e58b3ec86508adab926d7f4` (LGPL-3.0). The router does not independently download, verify, install or execute the selected file. The pin preserves the reference; it is not a cryptographic audit of the skill contents. Always review licensing and any commands/scripts before importing or executing downstream.

## Suggested dogfood

Run the exact same Godot puzzle mission in two isolated branches: Codex without external skills vs Codex after a **reviewed, pinned** `godot-genre-puzzle` guidance selection. Evaluate with existing capture and playtest services (runtime errors, required mechanics, replay state and visual review). Fixture routing tests prove only deterministic selection, **never gameplay improvement**. Do not describe the outcome as a true win until both branches have comparable real-project evidence.
