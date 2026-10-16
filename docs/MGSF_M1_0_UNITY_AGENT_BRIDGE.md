# MGSF-M1.0 Unity Official Agent Bridge / Dual-Engine Game Factory

## Status: incubation / runtime HOLD

The existing Godot capture and EdenSpark evidence path remain unchanged. This milestone adds a **non-vendored, opt-in** Unity 6+ CLI bridge. A live Unity Editor, actual Unity test run, Unity official Codex plugin, and gameplay proof are **not** supplied by this repository.

## Dependency qualification

- Upstream: https://github.com/Unity-Technologies/unity-agent-plugin
- Codex manifest at reviewed revision: 0.1.8-beta
- Reviewed upstream commit: cf6b2da24e424b0a60d560a57f39f676cb6f79f3
- License: Unity Companion License; do not copy the upstream skills into this repository without a license review.
- Local executor is required. Unity CLI and the Editor run against the developer's local machine.
- The plugin is **not auto-installed** by MGSF. The read-only lock file documents an explicit, separately approved setup.
- Unity Editor requires Unity 6+. Editor-driving Pipeline operations require com.unity.pipeline; the batch test command does not.
- Upstream docs may evolve: verify commands and package versions before live use.

Official Codex opt-in commands (run manually in the target local environment):

    codex plugin marketplace add Unity-Technologies/unity-agent-plugin
    codex plugin add unity@unity-agent-plugin
    codex plugin list

Unity CLI and Pipeline setup follow the official unity-cli skill; do not run remote install scripts blindly. Back up/commit your Unity project first.

## MGSF commands

    mgsf engine-adapters
    mgsf unity-probe /path/to/UnityProject
    mgsf unity-test /path/to/UnityProject --mode EditMode
    mgsf unity-test /path/to/UnityProject --mode EditMode --execute

The test command is a **dry run by default**. Only --execute runs an installed Unity CLI. Both commands are constrained to a Unity project with Assets/ and ProjectSettings/ProjectVersion.txt declaring Unity 6+. The probe runs only a read-only status command. No arbitrary C# eval, user-supplied Unity CLI arguments, Pipeline package mutation, plugin installation, or build/deployment is performed.

The test command uses the official "unity test <project> --mode EditMode --output <path> --timeout <seconds> --format json" entrypoint. It runs without shell=True, with an explicit timeout and dedicated evidence path, and accepts a PASS verdict only when the CLI succeeds and fresh NUnit output contains positive passing test counts with no failures. A failing/missing/malformed report is FAIL. An unavailable CLI is recorded, not silently installed.

## Evidence contract

All Unity records include: schema_version, engine, service, Unity Editor version from the project, project path, evidence class, verdict and **status=HOLD**. Recorded CLI results include executable argv, exit code and hashed stdout/stderr. Reports are hashed as SHA-256. Console contents are not copied to the evidence JSON, reducing accidental disclosure.

- Probe READY proves only Editor connectivity. It is never gameplay proof.
- Test PASS means the reported Unity tests passed. It is not an endorsement of gameplay quality.
- Mocked tests and deterministic fixtures are contract verification, not live Editor evidence.
- The existing Godot runtime and promotion logic are not changed.
- Unity promotion needs future evidence: CLI/Editor identity, running gameplay and frame progression, timestamped screenshots/video, input replay, console/runtime checks, artifacts and hashes, real-project verification, and license review.
- Do not call prototype-promote on Unity probe/test records; they deliberately do not meet the prototype promotion schema.

## Comparison boundary

The registry publishes two distinct adapters: Godot (active direct capture) and Unity (incubation CLI). A future paired-engine benchmark should take the same specification and compare reproducible build/test/play evidence, human review, time and direct cost, without granting fixture-only results any promotion status.

## Verify contract without Unity

    python -m pip install -e ".[dev]"
    pytest -q tests/test_unity_agent_bridge.py tests/test_catalog.py
    mgsf validate-catalog
    mgsf engine-adapters

The GitHub Actions unity-adapter-contract job runs these checks without Unity licenses, installations, or paid cloud resources.
