# MGSF-M0.9.1: Godogen Live Dogfood / Gameplay State Verification

## Goal and evidence scope

Make an actual Godot 4 .NET process accept deterministic input actions, change the visible game state, record a timed JSON trace, and render a 15-second MP4. Machine-check signed player-state deltas against mission criteria.

A hand-authored engine dogfood game is **not** evidence that Godogen or Codex autonomously generated a game. Two statuses are tracked separately:

- runtime state: PASS / ITERATE / HOLD
- Godogen autonomous generation: **HOLD** until independently verified

This is a new incubation service and leaves MGSF Godot Capture, Playtest Report, EdenSpark and MAF untouched.

## Evidence path

~~~text
Mission (input windows, signed deltas, idle stability)
   -> Godot 4 .NET / C# build
   -> Godot import
   -> scripted Godot Input actions in actual _PhysicsProcess
   -> Godot PNG movie frames + same-process JSON state trace
   -> FFmpeg MP4 encoding and FFprobe
   -> input/tick/state correlation
   -> verified runner hashes, preserved evidence
   -> runtime PASS (autonomous HOLD)
~~~

Input is scripted, not human telemetry. The actual C# scene renders and runs in Godot. This is not a Python-only simulation.

## Run actual engine dogfood

GitHub Actions workflow: .github/workflows/godogen-live-state.yml.
It installs Godot 4.7.2 Mono/.NET, .NET 9 SDK, FFmpeg and Xvfb.

~~~bash
mgsf godogen-state-dogfood \
  fixtures/godogen/gyro-live \
  fixtures/godogen/mission-gyro-live.json \
  --execute --godot /path/to/Godot_v4.7.2-stable_mono_linux.x86_64 \
  --output-root ci-evidence/godogen-live-state
~~~

Without --execute no engine run starts. The sample fixture is kept in-repository. Runner refuses projects without .mgsf-gyro-dogfood marker, old capture frames, existing video or state trace, and failed build/import/capture/encode steps.

## Mission contract

~~~json
{
  "schema_version": 1,
  "mission_id": "gyro-lab-state-001",
  "state_checks": [
    {"id":"tilt-right","start_tick":30,"end_tick":120,"axis":"x","input":"right","min_delta":80},
    {"id":"tilt-left","start_tick":180,"end_tick":270,"axis":"x","input":"left","max_delta":-80},
    {"id":"neutral-stable","start_tick":300,"end_tick":390,"axis":"x","input":"idle","max_abs_delta":0.001}
  ]
}
~~~

The complete mission is fixtures/godogen/mission-gyro-live.json. Every sample must have an increasing integer tick, valid input label and finite x/y state. Every window boundary sample must be present. Input labels in the entire window must agree with the expected action, including the neutral/no-input interval.

## Offline verification

~~~bash
mgsf godogen-state-verify \
  <godot-project> fixtures/godogen/mission-gyro-live.json \
  --trace screenshots/state-trace.json \
  --video screenshots/proof.mp4 \
  --runner-record <run-evidence/runner.json> \
  --output-root evidence/godogen-state
~~~

Use --fixture for synthetic testing: fixture evidence always HOLDs. No successful runner record: HOLD. Missing gameplay deltas with a recorded runner: ITERATE.

Output evidence/godogen-state/<mission_id>/<run_id> contains state-evaluation.json, state-trace.json, proof.mp4, and runner.json (for the dogfood command). Trace and video SHA-256 are preserved. Paths must resolve inside the project.

## Still unverified

- Godogen/Codex creating a new game autonomously (requires an actual separate pinned source + Codex run).
- A general state instrumentation adapter for arbitrary Godot games.
- Human playtesting, gameplay quality, license/release promotion.

MGSF-M0.9.2 can join autonomous Codex construction proof and engine state proof with source-aware provenance. A state PASS is never sufficient by itself to promote an autonomous game generator.
