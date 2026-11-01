# MGSF Sound Identity Lab M0.6: Real Sound Experience Lab

M0.6 adds an **opt-in Godot Master bus PCM recorder** and a separate offline integrity/quality analyzer. It can collect mixed audio samples on a non-Dummy Godot audio driver during real gameplay. These samples are not independent proof of hardware speaker output, subjective experience, or synchronized player action. Promotion remains **HOLD**.

## Manual capture, no auto-injection

Copy 'adapters/godot/mgsf_sound_capture.gd' into a **trusted** Godot 4 project and manually register an Autoload called 'MGSFSoundCapture'. The adapter only starts if:
- MGSF_SOUND_CAPTURE_CONSENT=YES
- MGSF_SOUND_CAPTURE_DIR is an absolute directory outside the Godot project, with no existing output files
- audio driver is not Dummy
- optional MGSF_SOUND_CAPTURE_DURATION_MS (500-10000, default limited to at least 500ms)

Run the game normally with actual audio output, **not --headless**. The adapter temporarily attaches AudioEffectCapture to Godot Master bus, records PCM16 stereo for up to 10 seconds, removes its effect, and writes two files to the opted-in directory:
- 'master-bus.wav': the engine's Master bus samples
- 'capture-manifest.json': origin claim, driver name, consent, sample rate/count, monotonic clock start/end, discarded frames, SHA-256 and optional markers

From game code you can call 'MGSFSoundCapture.mark_event("start-01", "start")' to timestamp a transition on the same Godot monotonic clock. Kinds: start, switch, stop, loop, input. The markers are **claims by the game**, not separately calibrated acoustic event times.

Example Windows PowerShell setup before launching the trusted game:

~~~powershell
$env:MGSF_SOUND_CAPTURE_CONSENT = "YES"
$env:MGSF_SOUND_CAPTURE_DIR = "C:\Users\Public\mgsf-audio-test"
$env:MGSF_SOUND_CAPTURE_DURATION_MS = "5000"
~~~

Do not capture confidential voice chat, protected music or background audio without authorization. The adapter captures *all audio routed through Master* and does not ask for microphone access.

## Analyze locally

~~~bash
mgsf sound-experience /path/to/capture-manifest.json /path/to/master-bus.wav --output-root evidence/sound-experience
# Synthetic fixture-only test:
mgsf sound-experience fixtures/capture-manifest.json fixtures/master-bus.wav --fixture
~~~

The parser checks explicit consent, source claim, non-Dummy driver, checksum, PCM sample count/format/rate, bounded file size (48 MiB) and length (up to 90 seconds), monotonic capture clock, optional markers, ring buffer drops and sample-rate/frame counts. It calculates 50ms RMS/peak windows, long silence, clipping ratio and possible click jumps near claimed loop markers. Reported start/stop clock duration is compared against the PCM duration, with >100ms drift flagged. **This is not measured input-to-audible latency**, and a sample discontinuity is not proof of an audible click.

The output is 'evaluation.json', with input hashes, flags, PCM heuristics, driver/provenance claims and **actual_speaker_output_verified=false; promotion_gate=HOLD** even on technical PASS. No files are written into the target Godot project and no audio uploaded anywhere.

## Design constraints and outstanding verification

- Engine Master bus PCM is distinct from OS loopback: independently capturing the desktop output (for instance, Windows WASAPI loopback) can corroborate the source later. Microsoft's WASAPI loopback docs: https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording
- Godot AudioEffectCapture docs: https://docs.godotengine.org/en/4.6/classes/class_audioeffectcapture.html
- Godot may create its own runtime cache; adapter does not rewrite scene files.
- Avoid headless Dummy audio: it produces no reliable audible output. No authenticated capture/device attestation is implemented.
- CI tests use synthesized WAV and a synthetic manifest. The real non-Dummy capture pathway remains **unverified by CI** until a user runs the adapter on a real machine.
- Live Windows/Linux device, source legitimacy, M0.4 event/session linkage, calibrated audio/video synchronization, privacy and real-person listening reviews are all pending.
- No remote recording, arbitrary shell, SaaS, CI microphone permissions, credentials or automatic promotion.

## Acceptance gates

1. Genuine opt-in non-Dummy game recording with source provenance.
2. Verify track and scene wiring with direct gameplay capture.
3. Independent loopback recording and calibration of capture clock against audio output.
4. No lost frames or unexpected silence/clipping, verified across target platforms.
5. Human listening and licensing review before any promotion. Until then: **incubation / HOLD**.
