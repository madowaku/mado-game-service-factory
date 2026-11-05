# MGSF-STUDIO-M0.2: Creative Pipeline Integration

Status: **incubation / integration candidate**. This change is stacked on the still-unmerged M0.1 Draft PR. It does not merge or publish anything.

## What is connected

```text
game hypothesis (M0.1 mission.json)
    |
    v
mgsf studio-pipeline-pack
    |
    +-> builder-prompt.md (Godot implementation + optional art/audio stages)
    +-> qa-prompt.md (distinct human/agent QA role)
    +-> studio-pipeline.json (real MADO Cockpit CLI sequence, NOT invoked)
    |
    v
MADO Cockpit (existing, separate local install)
  mission create -> operator start -> launch builder -> submit evidence
    -> Cockpit snapshot/handoff -> launch qa -> qa_report -> verdict
    |
    +-> game engine's MCP (configured independently in project)
    +-> optional Asset Foundry / MADO Game Audio Loop outputs
    |
    v
mgsf godot-capture (existing real engine adapter)
    |
    v
mgsf studio-pipeline-eval
    |
    +-> SHA-256 + path + PNG header + source revision + adapter criteria checks
    +-> optional creative artifact receipts (byte integrity only)
    |
    v
READY_FOR_QA / ITERATE   (never PROMOTE)
```

The Cockpit Operator available at the inspected revision has **builder and qa** as its only executable roles. Therefore producer/gameplay/art/audio responsibilities are *sections* of the Builder brief, not pretend separately launched agents. Independent QA is delegated to Cockpit's existing QA worker and immutable handoff. See [MADO Cockpit](https://github.com/madowaku/mado-cockpit) and [Claude Code Game Studios](https://github.com/Donchitos/Claude-Code-Game-Studios).

## Generate the handoff

```sh
mgsf studio-pipeline-pack fixtures/studio/mission-isometric-room-001.json \
  --output-root missions/studio-pipeline
```

Inspect `missions/studio-pipeline/isometric-room-001/` for:
- `studio-pipeline.json`: structured `argv` recipe for **actual supported** `mado-cockpit` commands, explicit ordering/placeholder constraints
- `builder-prompt.md`: minimal gameplay build, art and audio workstreams and proof
- `qa-prompt.md`: independent QA scope, source hash and direct media review

This command is read/write local only and does not execute Cockpit, Codex, MCP, assets, or audio. The recipe must be reviewed, supplied with real operator/session IDs and workspace-relative evidence paths, and executed intentionally from the correct project root. `mado-cockpit init` and an engine MCP configuration are prerequisites. The Cockpit CLI automatically captures `git_diff` from a changed worktree and `session_trace` from the actual recorded Codex session. The Builder supplies a `test_result` file; QA supplies a `qa_report`. The Codex agent must never be considered proof of a real engine run without the relevant runner and artifact evidence.

An existing Cockpit capability registry may require resolving/binding allowed capabilities before `operator launch`; these are **not automatically granted** by MGSF. Operator ID and QA result IDs are discovered during execution. The CLI recipe intentionally contains placeholders, so it is not a fire-and-forget shell script.

### Optional creative workstreams

- **Art**: use [MADO Asset Foundry](https://github.com/madowaku/mado-asset-foundry) or a project-approved art workflow for asset manifests and visual reviews. Its `maf` commands are not automatically invoked.
- **Audio**: use [MADO Game Audio Loop](https://github.com/madowaku/mado-game-audio-loop) for source-bound recipe sets and audition/review. The M0.2 bridge only verifies the supplied output file digest, not whether it has been auditioned.

Copy or stage the selected approved manifest/recipe into the game project's reviewable worktree. Then supply the corresponding project-relative path and exact SHA-256 in a **creative receipt manifest**:

```json
{
  "schema_version": 1,
  "mission_id": "isometric-room-001",
  "art": {
    "source": "mado-asset-foundry",
    "path": "assets/art-manifest.json",
    "sha256": "<64 lowercase hexadecimal characters>"
  },
  "audio": {
    "source": "mado-game-audio-loop",
    "path": "audio/recipe-set.json",
    "sha256": "<64 lowercase hexadecimal characters>"
  }
}
```

This example is a template with placeholders, not a verified manifest. For requested tracks, missing, modified, duplicate-by-field, unexpected, wrong-source, outside-project or mismatched artifact receipts fail closed. Project-local file integrity is *not* game asset usability, a playtest, proof of authorship, or human art/audio approval; Cockpit QA must inspect these independently.

## Real Godot smoke verification

The existing GitHub CI already runs Godot **4.7.2**, with a pinned `madowaku/vertical-slice` checkout at `f0514229d7f2036ec25646d09e3647c8d870dadb`. Existing `mgsf godot-capture` creates real PNG screenshots, input timeline, runtime log, and `adapter_eval.json`. M0.2 does not replace that adapter and does not pretend a copied image is direct gameplay.

After `mgsf godot-capture`:

```sh
mgsf studio-pipeline-eval \
  vendor/vertical-slice \
  fixtures/studio/mission-vertical-slice-smoke-001.json \
  ci-evidence/godot-capture-adapter/vertical-slice-c6-direct/adapter_eval.json \
  --source-sha f0514229d7f2036ec25646d09e3647c8d870dadb \
  --output-root ci-evidence/studio-pipeline
```

Output: `ci-evidence/studio-pipeline/vertical-slice-smoke-001/pipeline-eval.json`.

A successful **real** adapter run with consistent output and SHA yields `READY_FOR_QA`, not `PASS` or `PROMOTE`. The file hashes and paths, `project.godot`, complete adapter criteria, source commit, direct-capture metadata, runtime/preflight log, input timeline and PNG headers/dimensions are checked. A mismatched SHA or altered artifact returns `ITERATE`. A recorded `adapter_eval.json` still must be treated as locally generated evidence rather than independent cryptographic attestation.

For the isometric mission with both art and audio workstreams, add `--creative-manifest <path>` after staging the two actual outputs. No creative receipts are needed for the gameplay-only smoke mission.

**Compatibility constraint**: the current Godot adapter expects the `res://scenes/capture/mgsf_c6_capture.tscn`-style scene and fixed direct-capture file names. This is not yet a generic Godot recorder, and a new project must supply a compatible capture scene or get a new adapter.

## M0.2 verification claims

- `studio-pipeline-pack`: a deterministic recipe using real Cockpit CLI verbs, but it does not invoke paid models or start sessions.
- `studio-pipeline-eval`: verifies locally recorded engine artifacts, SHA, and optional creative output receipts. It does not launch Godot.
- `READY_FOR_QA`: the retained capture is eligible for separate QA review, **not** proof that independent QA took place.
- CI real capture: verifies that the existing `vertical-slice` scene runs and its artifact contract is satisfied. It **does not** mean the isometric M0.1 concept game has been generated.
- Source revision, engine availability, art/sonic taste, fun, permissions, cost, and distribution still require explicit decisions.

## Validation and next boundary

```sh
python -m pytest tests/test_studio_pipeline.py -q
python -m pytest -q
mgsf validate-catalog
```

CI executes `studio-pipeline-pack` and `studio-pipeline-eval` after the real Godot direct capture. CI requires `READY_FOR_QA` with `promotion_eligible=false`. Unit tests that inject synthetic PNG headers only exercise schema/integrity logic and **are not real captures**.

**M0.3 target:** an end-to-end local MADO Cockpit Builder→QA run with actual Codex sessions, Godot MCP interactions, optional approved art/audio workstreams, Game Test Player behaviors and a human-taste review. Connect these with immutable Cockpit artifact IDs, and only then consider an independently enforced promotion policy. No autonomous publishing or paid model invocation should be added silently.
