# MGSF-M0.9.2: Autonomous Godogen Generation / State-to-Frame Proof Gate

## Evidence and trust boundaries

This milestone introduces **independent video-pixel measurement** plus a separate Godogen/Codex source-provenance gate. The CI uses the M0.9.1 *hand-authored* GYRO scene and does not claim AI-created gameplay.

The image verifier decodes real RGB frames using FFmpeg, measures the color-matched player centroid across the FULL video frame, and checks it against Godot input/state samples from the same run.

The autonomy verifier refuses fixture promotion and requires a pinned upstream Godogen intake, actual recorded Codex runner, generated source fingerprint, independent engine rebuild/import/replay, state contract PASS, and frame-alignment PASS.

A local PASS is only a consistent, reproducible evidence contract, NOT cryptographically signed remote attestation or definitive AI authorship. Humans can alter local files and runner records.

## Pipeline

~~~text
Pinned clean Godogen checkout + new isolated project
  -> MGSF-M0.9 safe intake
  -> Opt-in Codex build / runner / generated-source SHA-256 inventory
  -> Opt-in, separate Godot .NET source rebuild and movie capture
  -> Godot input-labeled state trace and H.264 video
  -> M0.9.1 state verification: right / left / idle checks
  -> M0.9.2 FFmpeg frame decoding: color centroid vs X/Y state
  -> M0.9.2 Codex+intake+source+state+frame provenance gate
  -> PASS / ITERATE / HOLD
~~~

All components are opt-in when running untrusted Codex-generated game code.
No paid asset key is configured, and no autonomous release or publication is attempted.

## CI: real image measurement, no Codex credentials

The dedicated GitHub Actions workflow is .github/workflows/godogen-live-state.yml.
It runs the existing GYRO fixture in Godot 4.7.2 .NET, builds a 15-second
movie and state trace, then calls the following extra verifier:

~~~bash
mgsf godogen-frame-proof \
  fixtures/godogen/gyro-live fixtures/godogen/mission-gyro-live.json \
  --trace screenshots/state-trace.json \
  --video screenshots/proof.mp4 \
  --state-evidence <state-evaluation.json> \
  --output-root ci-evidence/godogen-live-state
~~~

The probe contract specifies FPS, game-world dimensions, tracked player RGB,
pixel tolerance/count range, and five check ticks. The raw decoded frame is
not replaced with the agent's narrative or a synthetic screenshot.

Expected with hand-authored fixture: frame PASS; autonomy remains HOLD.

## Real autonomous-generation procedure

Run only on a separate, expendable environment with a configured Codex CLI,
Godot .NET, the compatible .NET SDK, FFmpeg and a working display/Xvfb:

~~~bash
git clone https://github.com/htdt/godogen.git ./vendor/godogen
SHA=$(git -C ./vendor/godogen rev-parse HEAD)
mgsf godogen-intake ./vendor/godogen ./runs/gyro-codex \
  --expected-sha "$SHA" --apply
mgsf godogen-loop ./runs/gyro-codex \
  fixtures/godogen/mission-gyro-live.json \
  --execute --godot /path/to/Godot.NET.binary \
  --output-root evidence/godogen
mgsf godogen-generated-capture ./runs/gyro-codex \
  fixtures/godogen/mission-gyro-live.json \
  --execute --godot /path/to/Godot.NET.binary \
  --output-root evidence/godogen-generated
~~~

The Codex prompt now requires the agent to build a playable Godot C# game,
accept command-line trace/run-id/mission-id parameters, implement Godot
Input.ActionPress/ActionRelease windows, record time-aligned state samples,
and render a character in the declared color. An external MGSF runner then
replays the generated game separately and verifies its visual behavior.

The generated runner refuses the hand-authored GYRO fixture marker, altered
staged instructions, pre-existing screenshots, absent engine artifacts, and
source changes during replay. Running untrusted code remains risky: Codex
workspace-write is not an OS-security boundary. Never run on a machine with
secrets or sensitive source files.

After a successful Codex iteration N and a generated replay run-id:

~~~bash
mgsf godogen-autonomy-gate ./runs/gyro-codex \
  fixtures/godogen/mission-gyro-live.json \
  --frame-proof evidence/godogen-generated/gyro-lab-state-001/gen-<id>/frame-proof.json \
  --state-evidence evidence/godogen-generated/gyro-lab-state-001/gen-<id>/state-evaluation.json \
  --godogen-evaluation evidence/godogen/gyro-lab-state-001/iteration-<N>/evaluation.json \
  --codex-runner evidence/godogen/gyro-lab-state-001/iteration-<N>/runner/runner.json \
  --output-root evidence/godogen-autonomy
~~~

Expected without a real pinned Codex run: HOLD. Fixture evaluations never
promote even when mock values match.

## Scope

- Source fingerprints are a reproducibility check, not cryptographic proof
  that a particular AI authored a file.
- The RGB color tracker is for high-contrast 2D scenes. It does not handle
  arbitrary sprites, occlusion, 3D depth or dynamic camera transformations.
- A valid video does not prove gameplay is fun or ready to release.
- Asset licensing, human testing and publisher submission remain outside scope.
- Compatible with existing MGSF EdenSpark and gameplay-capture services.
