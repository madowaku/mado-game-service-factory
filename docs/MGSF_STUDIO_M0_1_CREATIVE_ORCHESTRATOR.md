# MGSF-STUDIO-M0.1: Creative Studio Orchestrator

Status: **incubation**. This is an advisory planner and evidence-receipt verifier, **not** an autonomous studio or a live engine integration.

## Origin and adaptation

Inspired by [Donchitos/Claude-Code-Game-Studios](https://github.com/Donchitos/Claude-Code-Game-Studios), reviewed at upstream `05ad7c8a5b8aa2aa86bbd3439ae7cf7295cac418` (MIT). The reference uses specialized roles, producer handoffs, visual checks, and skill testing. MGSF uses independently written minimal Python contracts rather than importing 49 personas, 74 skills, or shell hooks. Upstream templates and hooks are **not** installed or executed.

## Why this belongs in MGSF

MADO Cockpit already handles real Codex sessions, worktrees, Builder-to-QA handoff, capability policy, evidence snapshots, and human-decision gates. Rebuilding those functions would add risk. MGSF owns only the **game-domain plan**, capability hints, required evidence kinds, and an evidence triage gate. These are portable across Codex and Claude Code because they are JSON and do not embed a provider-specific agent runtime.

```text
user game hypothesis
    |
    v
mgsf studio-plan --> studio-plan.json (advisory only)
    |
    +-- producer: brief
    +-- gameplay: source_change + test_result
    +-- art (optional): asset_manifest + visual_review
    +-- audio (optional): audio_manifest + audio_review
    +-- qa: qa_report + gameplay_capture + runner_record
    |
    v
MADO Cockpit execution / independent QA (FUTURE M0.2)
    |
    v
mgsf studio-gate --> HOLD / ITERATE / READY_FOR_REVIEW
    |
    v
human / independently verified runtime gate (NOT implemented here)
```

## CLI

Run from the repository root with the Python package installed (e.g. `pip install -e .`):

```sh
mgsf studio-plan fixtures/studio/mission-isometric-room-001.json \
  --output-root missions/studio
```

Output: `missions/studio/isometric-room-001/studio-plan.json`.

A mission JSON requires `schema_version: 1`, safe lowercase `mission_id`, nonempty `title`, `hypothesis`, and `success_criteria`. `engine` is `godot` (default) or `edenspark`. `workstreams` contains `gameplay` plus optional `art` and `audio`. Every plan includes producer and QA. The producer precedes creative tasks; QA depends on all selected tasks.

The role's `capability_hint` is **not** a capability grant. Resolve permissions, cost, provenance, and actual provider in Cockpit before agent execution.

## Evidence manifest

A separate worker or harness may collect files under the project root. The caller must supply exact SHA-256 digests; the gate rehashes each file. Example shape (only partial receipts shown):

```json
{
  "schema_version": 1,
  "mission_id": "isometric-room-001",
  "evidence_class": "recorded",
  "tasks": {
    "producer": [
      {"kind": "brief", "path": "docs/brief.md", "sha256": "<64 lowercase hexadecimal characters>"}
    ],
    "gameplay": [],
    "art": [],
    "audio": [],
    "qa": []
  }
}
```

`sha256` must be a real 64-character lowercase hex digest, not the placeholder above. Paths are relative to the passed project root. The verifier rejects missing files, hash mismatches, path traversal or symlink escapes, duplicate kinds, unexpected kinds, and unknown tasks. It also reports every missing required evidence kind.

```sh
mgsf studio-gate ./path-to-game \
  fixtures/studio/mission-isometric-room-001.json \
  ./path-to-game/.mgsf/studio-evidence.json \
  --output-root evidence/studio
```

Output: `evidence/studio/isometric-room-001/studio-gate.json`.

## Gate semantics

| Status | Meaning | Promotable? |
|---|---|---|
| `HOLD` | Fixture input, even if every checksum matches | **No** |
| `ITERATE` | Recorded evidence is missing or invalid | **No** |
| `READY_FOR_REVIEW` | Recorded receipts match local files, but independent QA/runtime proof is still required | **No** |

**No M0.1 status means the game ran.** A file named `gameplay_capture` is not automatically a verified direct screenshot. Content, runner authenticity, source revision, and human play experience must be inspected by a separate gate. File receipts do not establish that Codex, Godot, EdenSpark, or Game Test Player ran. The schema does not yet verify evidence provenance beyond file existence and SHA-256.

## Safety and cost

- M0.1 uses the Python standard library, calls no model, launches no process, and makes no network request.
- It does not install upstream Claude hooks, auto-grant agent tools, publish a game, merge code, or authorize billed resources.
- MADO Cockpit remains responsible for isolation, capability grants, spending policy, independent QA worktrees, and human-decision escalation.
- Human decisions include creative-direction changes, privacy, cost, publishing, and deletion.
- Keep direct captures and test logs in their source systems and retain provenance; never label fixtures as real playtests.

## Validation

```sh
python -m pytest tests/test_studio_orchestrator.py -q
python -m pytest -q
mgsf validate-catalog
```

M0.1 acceptance: role selection, dependency graph, safe paths, checksum checks, fixture HOLD, recorded evidence review-only, and catalog validation. Unit tests use synthetic local files and do **not** constitute real game dogfood.

## Next boundary: M0.2

Integrate a **single** game mission with MADO Cockpit's real worker and QA contracts, using Godot MCP and Game Test Player. Require recorded engine input, actual gameplay capture, runtime logs, immutable evidence hashes, and a distinct QA worker. Only a later independent promotion gate can issue a real-world PASS. Add optional Art Director and Sound Identity Lab routing after gameplay and QA have reliable evidence.

M0.3 can add a measured `skill-test` / `skill-improve` loop, comparing task outcomes and cost before and after a skill change. Text lint scores alone must not be advertised as behavioral improvements.
