# MGSF-M0.9.3: Real Codex Generation Dogfood / End-to-End Autonomy Qualification

## Goal and actual outcome

The previous milestones established a pinned Godogen intake, a Codex loop,
real Godot .NET state tracing, and independently decoded frame-to-state
alignment. M0.9.3 adds ONE bounded command that walks the full chain and
writes an inspectable qualification report on every attempted live run.

**This source revision is NOT itself a live generated-game PASS.** The
credential-free GitHub Actions suite tests the command contract with stubs;
it does not have an authenticated Codex CLI. A live PASS is only legitimate
after the command has actually run in an isolated environment with a local
Codex login, compatible Godot .NET binary, .NET SDK, FFmpeg, and display/Xvfb.

## The explicit qualification sequence

~~~text
Preflight (no mutation, default)
  - Pinned clean htdt/godogen source + trusted Git origin
  - New and nonoverlapping target directory
  - Mission with success_criteria, signed state windows, pixel probe
  - Codex, Godot .NET, dotnet SDK, ffmpeg, ffprobe, Xvfb availability
       |
       v
--execute AND --accept-generated-code-risk
  - Stage pinned upstream into a NEW isolated project (no publish.sh)
  - Start bounded Codex exec workspace-write generation
  - Save prompt, Codex stdout/stderr hash, agent result, source hashes
  - Require M0.9 recorded build/import/launch and original movie PASS
  - Independently build/import/run the GENERATED game again
  - Save new per-run state/video without clobbering Codex original
  - Verify input-state directions and idle stability
  - Independently decode and compare real pixel centers across five ticks
  - Bind pinned source + generated source + Codex runner + state + frames
  - Write qualification.json: PASS / HOLD / ITERATE
~~~

**No Codex operation is launched by preflight.** An executed run is
fail-closed. If generation, capture or proof fails, the report remains HOLD
with the failure stage and relevant evidence paths. Every report includes
real_codex_observed and independent_game_replay_observed booleans, which are
not inferred from a fixture or the agent narrative.

## Prerequisites

- Clone a specific revision of htdt/godogen into a fresh vendor directory.
- Install the local Codex CLI and authenticate using its ordinary local
  account sign-in. Never paste a token into a chat, script or GitHub log.
- Install a Godot 4 .NET/Mono build, a matching .NET SDK, FFmpeg and FFprobe.
- On Linux use Xvfb. On Windows with an interactive desktop, use --no-xvfb.
- Use a disposable VM or purpose-built container with no secrets. Godogen
  instructions and Codex-generated C# are UNTRUSTED local code.
- Do not store paid asset-service API keys in the generated project.
- Do not run GitHub Actions with an injected Codex access token.

CLI compatibility: Codex exec supports --sandbox workspace-write,
--output-schema, --output-last-message and "-" for prompt stdin.
The integration never requests danger-full-access or bypass approvals.

## Bash example (Linux / WSL with Godot .NET and a virtual display)

~~~bash
python -m pip install -e ".[dev]"
git clone https://github.com/htdt/godogen.git ./vendor/godogen
SHA="$(git -C ./vendor/godogen rev-parse HEAD)"

# Safe: read-only readiness report; no target directory is created.
mgsf godogen-real-qualify \
  ./vendor/godogen ./runs/gyro-codex-live-001 \
  fixtures/godogen/mission-gyro-live.json \
  --expected-sha "$SHA" \
  --godot /path/to/Godot_v4.7.2-stable_mono_linux.x86_64 \
  --output-root ./evidence/gyro-codex-live

# Run ONLY in an expendable/sandboxed local environment, after reviewing
# the pinned upstream and understanding that real AI and game code will run.
mgsf godogen-real-qualify \
  ./vendor/godogen ./runs/gyro-codex-live-001 \
  fixtures/godogen/mission-gyro-live.json \
  --expected-sha "$SHA" \
  --godot /path/to/Godot_v4.7.2-stable_mono_linux.x86_64 \
  --output-root ./evidence/gyro-codex-live \
  --execute --accept-generated-code-risk
~~~

On Windows PowerShell, the same command can be invoked with the absolute
Godot .NET .exe path and --no-xvfb, running from an interactive desktop.

If a run fails, choose a NEW target directory for the next attempt.
There is no overwrite/force option. Codex generation cost depends on the
account/plan; Godot and FFmpeg are free software, while source integrations
with external paid asset APIs remain disabled in this MGSF contract.

## Evidence and failure modes

~~~
evidence/gyro-codex-live/
  qualifications/gyro-lab-state-001/codex-<uuid>/qualification.json
  generation/gyro-lab-state-001/iteration-N/
    evaluation.json
    runner/{runner.json,prompt.txt,schema.json,answer.json,stdout.txt,stderr.txt}
    proof.mp4 (when the original generator run produced verified media)
  generated-replay/gyro-lab-state-001/gen-<uuid>/
    state-trace.json
    state-evaluation.json
    proof.mp4
    frame-proof.json
    runner.json
  autonomy/gyro-lab-state-001/gen-<uuid>/autonomy-evaluation.json
~~~

- READY means preflight found tools and valid inputs; it does NOT prove
  Codex authentication or a working GPU/display.
- BLOCKED means required tools were missing; no mutation happened.
- HOLD means real execution cannot be verified (missing runner, failure,
  invalid provenance, absent trace), and MUST NOT be promoted.
- ITERATE means a recorded runner is present but behavioral proof is
  incomplete or inconsistent.
- PASS means local cross-run evidence contract passed, NOT independent
  remote attestation, security, licensing, enjoyment or release readiness.

Debug the earliest failed stage in qualification.json. Original Codex
stdout/stderr hashes and engine step return codes remain inspectable under
the generated evidence directory. Never upload credentials, Codex home,
workspace .env files, or user-level configuration to GitHub.

## CI proof and boundaries

The default GitHub Actions CI runs tests/test_godogen_qualification.py,
with synthetic Git checkout and mocked tool availability plus stubbed
Codex/engine responders. The integration test checks both successful
contract wiring and fail-closed behavior. Synthetic fixtures never count
toward the public live dogfood verdict.

The separately verified M0.9.2 Godot state/frame workflow remains the
independent real-engine evidence baseline. The new M0.9.3 workflow itself
is NOT scheduled to execute an authenticated Codex CLI on GitHub-hosted
runners, where credentials and untrusted output would add unnecessary risk.

## Future qualification

To move incubation to a proven autonomous generator, record one real Codex
game created from a clean pinned Godogen intake, a separate reconstructed
state/frame PASS, provenance checks in autonomy-evaluation.json, and the
top-level qualification.json with autonomous_generation_qualified=true.
Manually review the preserved movie and project before any promotion.
