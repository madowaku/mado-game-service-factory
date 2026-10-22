# MGSF-M1.2 GodotEnv Reproducible Environment Bridge

Status: INCUBATION / REAL WINDOWS DOGFOOD HOLD

## Scope

Chickensoft.GodotEnv 2.17.0 installs Godot versions and addons. Engine activation changes a user-wide symlink and environment variable, so default project audits never call it. Existing MGSF capture and the direct-pinned-Godot CI path remain unchanged.

## Commands

    mgsf godotenv-audit fixtures/godotenv/sample --output-root evidence
    mgsf godotenv-audit /path/to/game --probe --output-root evidence
    mgsf godotenv-prepare /path/to/game --allow-global-switch --output-root evidence
    mgsf godotenv-prepare /path/to/game --allow-global-switch --install-addons --output-root evidence

Audit is read-only by default. The optional probe queries the active Godot path and runs Godot --version. Prepare requires explicit --allow-global-switch. Installing addons requires a separate --install-addons and refuses any existing addons/.addons tree. Commands use argument arrays (no shell) and timeouts.

## Input contract

Requires project.godot and a project-root pin (.godotrc, global.json with msbuild-sdks.Godot.NET.Sdk, or root *.csproj). Conflicting version/.NET-mode pins fail. Explicit version arguments avoid accidental use of parent-directory pins.

The optional addons.json/addons.jsonc may declare only HTTPS GitHub remotes pinned to full 40-character commit SHA. Branches, ZIP downloads, symlinks, traversal and custom installation/cache paths fail the reproducibility gate. This is more conservative than GodotEnv's upstream capabilities.

## Evidence and gates

Evidence/audit.json contains SHA-256 input hashes, normalized addon sources/commits, version and .NET mode, command plan, optional active engine/version observation and optional post-install addon file hashes.

- FAIL: missing/invalid pins, unsafe add-on manifest, engine version mismatch or command/addon verification failure.
- HOLD: static fixture only, inconclusive live probe, or declared addons not explicitly installed and fingerprinted.
- PASS: active engine matches pin with no addons; or explicit prepare plus verified installed addon snapshots.

PASS means environment evidence, not real gameplay, real Windows dogfood, complete transitive dependency verification, or upstream cryptographic artifact provenance. Post-install file hashes do not prove equality to the checkout SHA.

## Safe rollout

1. Keep default MGSF CI and screenshot adapter intact, add deterministic tests.
2. Manually run the separate disposable-runner workflow on Linux/Windows to verify GodotEnv 2.17.0 with Godot 4.7.2 no-dotnet.
3. Review dependencies, backups, working tree state and licenses before touching a real game.
4. Only promote the live environment after runner evidence exists. Independently require gameplay evidence for game-quality claims.

GodotEnv activation is user-wide and must be serialized between different projects. Upstream issue #295 reports addons install may hang; the adapter uses a 120-second timeout, but partial files may need manual cleanup. Windows symlinks may require Developer Mode/elevation; no automatic elevation occurs.

Sources: https://github.com/chickensoft-games/GodotEnv and https://www.nuget.org/packages/Chickensoft.GodotEnv/2.17.0
