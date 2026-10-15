# MGSF-M0.9: Godogen Intake / Autonomous Game Build & Visual Proof Bridge

## Scope and boundaries

MGSF stages the [htdt/godogen](https://github.com/htdt/godogen) **Godot 4 .NET/C# + Codex** runtime in a NEW game directory and optionally launches a bounded Codex game-build loop. It does **not** embed or execute the upstream publisher, replace existing MGSF/EdenSpark/MAF services, or treat a compile as gameplay proof.

Only Godot/Codex is supported in M0.9. Bevy, Babylon.js, Claude, GDScript compatibility, MAF provider wiring and commercial asset generation require separate evidence before activation.

This module is **incubation**. CI verifies a deterministic fixture/contract. No real Godogen game was generated or played as part of the fixture. Live dogfood is a separate gate.

## Safe source intake

Clone Godogen yourself in an isolated local workspace and review the exact commit. Copy the **40-character Git HEAD** SHA into the command. The adapter rejects a dirty checkout, a mismatch, source/target overlap, symlinks or special files, huge asset trees, and **any existing target path**. Default behavior prints a preview only.

~~~bash
git clone https://github.com/htdt/godogen.git ./vendor/godogen
git -C ./vendor/godogen rev-parse HEAD

mgsf godogen-intake ./vendor/godogen ./runs/godogen-001 \
  --expected-sha <PINNED_40_HEX_SHA>
mgsf godogen-intake ./vendor/godogen ./runs/godogen-001 \
  --expected-sha <PINNED_40_HEX_SHA> --apply
~~~

There is deliberately **no --force option**. The local upstream **publish.sh** is **never executed**. The intake copies the minimal manifest, godot.md, MIT LICENSE, and asset-gen skill into .agents/skills/ and writes .mgsf/godogen-intake.json with upstream file hashes and policy. It does not run untrusted scripts or download paid assets.

The staged files contain executable instructions and script sources, so their pinned provenance does not make them automatically safe to run. Review them before the explicitly opted-in Codex execution. Treat upstream files as untrusted.

## Mission and autonomous loop

Mission JSON:

~~~json
{
  "schema_version": 1,
  "mission_id": "tiny-gyro-001",
  "description": "Build a small playable movement prototype with a clear visual response.",
  "success_criteria": [
    "Directional input visibly changes position",
    "Game launches without runtime errors",
    "15-20 second proof clip demonstrates changing game state"
  ],
  "max_iterations": 2
}
~~~

Run in a separate Godogen game directory. No game creation, engine execution, or Codex invocation occurs until **--execute** is present:

~~~bash
mgsf godogen-loop ./runs/godogen-001 ./mission.json --execute \
  --codex codex --godot godot --dotnet dotnet \
  --output-root ./evidence/godogen
~~~

The loop performs up to three Codex iterations in workspace-write sandbox, returns a structured answer, captures stdout/stderr SHA-256 and launch timestamps, then independently invokes:

1. dotnet build
2. godot --headless --path PROJECT --import
3. godot --headless --path PROJECT --quit-after 5

All subprocesses use argument arrays (no shell string) and finite timeouts. The generated game's project.godot and C# project files must exist. The agent is directed to produce and inspect screenshots/proof.mp4. The adapter uses ffprobe to check a decodable video stream, at least 320x180 dimensions, and duration 14-22 seconds (encoding tolerance around the target of 15-20s). A valid video is copied and SHA-256 indexed into an MGSF evidence bundle.

**Costs:** GOOGLE_API_KEY, XAI_API_KEY and TRIPO_API_KEY are removed from the Codex subprocess environment. Upstream generation scripts are not invoked by intake. This does not guarantee a process cannot use credentials available elsewhere in its workspace, so keep the project isolated and do not store API secrets in it. No paid asset-generation permission is granted by M0.9.

## Proof statuses

- **PASS**: recorded successful Codex run, all agent action claims, zero reported errors, existing Godot C# project, successful independent build/import/launch checks and verified media.
- **ITERATE**: successful runner/probes but absent or invalid observable proof.
- **HOLD**: fixture, missing failed/unrecorded runner or independent engine checks. Fixtures never promote.

The result is *agent-mediated visual evidence*, not a human playtest, independent guarantee of gameplay correctness, or release approval. The existing MGSF **godot-capture** service remains the preferred source for direct gameplay frame/timeline evidence, while **prototype-promote** remains scoped to the existing EdenSpark contract unless explicitly upgraded.

To evaluate an offline fixture (which must remain HOLD):

~~~bash
mgsf godogen-eval <game-project> <mission.json> <agent-result.json> \
  --fixture --output-root ./evidence/godogen
~~~

Evidence structure:

~~~text
evidence/godogen/<mission_id>/iteration-N/
  evaluation.json
  proof.mp4               # only if a valid bounded MP4 was preserved
  runner/
    prompt.txt
    schema.json
    answer.json
    runner.json
    stdout.txt
    stderr.txt
~~~

## Activation checks

- Run the focused unit tests and the repository CI suite.
- Run one REAL Codex/Godogen game dogfood in an isolated project, with a pinned upstream SHA and available Godot **.NET** binary, .NET SDK and ffprobe.
- Verify engine-probe logs, media provenance and playable input changes by manually watching the clip. Media validity alone is not a gameplay-quality score.
- Only then consider integration with MAF licensing, MGSF gameplay-capture and AI Playtest Laboratory state replay. No release or game submission is allowed within the loop.
