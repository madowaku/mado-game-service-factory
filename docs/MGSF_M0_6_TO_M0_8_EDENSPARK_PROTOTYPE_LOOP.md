# MGSF-M0.6 to M0.8 - EdenSpark Agent-Native Prototype Loop

## Goal

Use EdenSpark as an external agent-native game runtime without turning MGSF into another game engine or another MCP client.

The execution split is deliberate:

```text
Neon Brainstorm / mission hypothesis
  -> MGSF mission pack
  -> Codex CLI
  -> EdenSpark project-provided MCP
  -> scene inspect / code / hot reload / play / input / screenshot / logs
  -> MGSF evidence evaluation
  -> autonomous retry
  -> PROMOTE / ITERATE / HOLD
```

EdenSpark owns editor and game actions. Codex owns MCP tool use. MGSF owns evidence, provenance, iteration limits, and promotion decisions.

## M0.6 - EdenSpark Agent-Native Engine Adapter

Commands:

```text
mgsf edenspark-plan missions/edenspark-neon-001.json
mgsf edenspark-eval <project> <mission.json> <result.json> --runner-record <runner.json>
```

A mission contains a hypothesis and observable success criteria. The generated prompt requires the agent to inspect the scene, compile or hot reload, start the game, simulate input, capture a screenshot, and check logs.

The adapter does not trust artifact names. Paths must stay inside the project, files must exist, and each preserved artifact is hashed with SHA-256.

## M0.7 - Autonomous Playtest Loop

```text
mgsf edenspark-loop <project> <mission.json> --max-iterations 3
```

MGSF invokes `codex exec` non-interactively with a strict JSON output schema. Each failed iteration is fed back to the next iteration. The loop stops on PASS or at the mission iteration cap.

The runner records:

- command and project working directory
- start/end timestamps
- return code
- stdout/stderr SHA-256
- structured agent result
- evaluated engine/playtest evidence

No publishing or catalog submission is part of the loop.

## M0.8 - Prototype Promotion Gate

```text
mgsf prototype-promote <evaluation-1> [<evaluation-2> ...]
```

Decision rules:

- `PROMOTE`: at least one non-fixture recorded run is PASS.
- `ITERATE`: live attempts exist, but none pass.
- `HOLD`: only deterministic fixture evidence exists.

This makes fixture-only CI useful for regression testing while preventing it from being mislabeled as a successful EdenSpark dogfood run.

## Evidence classes

### deterministic_edenspark_fixture

Synthetic or recorded contract data used only to prove calculation, CLI, and promotion behavior. It can never promote.

### recorded_edenspark_agent_mcp_run

A run created by the MGSF Codex runner in a real EdenSpark project. PASS additionally requires all required actions, zero reported runtime errors, at least one preserved artifact, and a successful `codex-exec` runner record.

This is agent-mediated engine evidence, not a human playtest measurement.

## Codex integration

The runner uses the current non-interactive Codex CLI shape:

```text
codex exec \
  --sandbox workspace-write \
  --ask-for-approval never \
  --output-schema <schema.json> \
  --output-last-message <result.json> \
  -
```

The EdenSpark project is expected to provide its own working MCP configuration. MGSF does not copy, rewrite, or guess EdenSpark MCP endpoints.

## Promotion beyond M0.8

A future Neon Brainstorm control-plane adapter can submit the same hypothesis to EdenSpark, Godot, Unity Spark, or Web runtimes and compare evidence under one promotion contract. That cross-engine tournament is intentionally outside this patch.
