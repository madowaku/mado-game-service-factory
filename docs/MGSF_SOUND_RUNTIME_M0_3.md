# MGSF Sound Identity Lab M0.3: Audio Gameplay Evidence (incubation)

## Why this exists

M0.2 validates user-exported WAV and prepares non-destructive Godot imports. M0.3 adds a process-level verification layer: a genuine Godot 4 process loads the hash-matched WAV, calls `AudioStreamPlayer.play()`, observes `playing`, stops, and reports state. This is **not sound output capture** and **not an actual game session**.

**Godot headless uses the Dummy audio driver**, so an engine-state PASS never proves audibility, latency, mixing quality, gapless loops, crossfades, human pleasure, or scene wiring. Promotion is always HOLD. Real gameplay and human listening are M0.4 prerequisites.

## CLI

```bash
# First apply vetted material from M0.2, after reviewing the source archive:
mgsf sound-identity export.zip /path/to/godot --apply --out evidence/import.json

# Real engine-state smoke, no scene writes:
mgsf sound-runtime /path/to/godot --godot /path/to/Godot --output-root evidence/sound-runtime

# Synthetic test inputs (e.g. CI) MUST be labeled:
mgsf sound-runtime /path/to/test-godot --godot /path/to/Godot --fixture
```

`--godot` is required; no hidden downloads, API calls, auth, telemetry, or third-party editor automation. The project must contain `audio/mgsf_sound_identity/sound_map.json` from M0.2, containing 1 to 12 imported tracks. The runtime verifier checks every WAV's path, size, symlink ancestry, and SHA-256 against that map **before** launching Godot. It does not edit scene files, change audio bus settings, or claim that the game actually used the track. Godot may generate a `.godot/` runtime cache in the inspected project.

## Evidence bundle

Written outside the Godot project:

- `input-spec.json`: absolute resolved paths and SHA-256 for bounded engine inputs
- `godot-run.json`: command, process result, duration and capped stdout/stderr
- `engine-state.json`: raw engine JSON with driver/version and ordered per-track observations
- `evaluation.json`: independent reconciliation, raw evidence SHA-256, technical PASS/FAIL, **promotion HOLD**

A success requires all expected tracks in the exact order, matching hashes and transition links, valid timestamps, independent `load_ok / started / stopped / loop_configured` checks, exit code 0, and the engine stdout success marker. Missing/malformed/forged/truncated logs and process failure cannot pass. A loop request proves only that engine loop mode was configured; not that a seamless repeat was heard.

## CI and acceptance

GitHub CI runs `pytest` including a genuine Godot engine subprocess on **synthetic WAV data**, tagged `synthetic_wav_real_engine_probe`. All CI success remains HOLD. The same runner can later inspect genuinely exported audio, with provenance and human review.

Promotion prerequisites not provided by this milestone:

1. Independently review license/provenance of a user-exported AMIX ZIP.
2. Demonstrate **real gameplay integration**, audio events synchronized with captured inputs/screenshots.
3. Capture actual mixed output through a supported audio driver/device or hardware loopback, and measure audible continuity/level.
4. Human listening and cross-platform checks (including Windows) and signed-off production-quality assessment.

## Threat model

Untrusted ZIP contents are vetted by M0.2; M0.3 only loads exact, hash-matched WAV in the dedicated directory and refuses symlink ancestry. The Godot project and executable are still executable software and should not be run on untrusted source without OS-level isolation. The engine JSON is an observation subject to provenance and spoofing, not independent cryptographic proof of real-world audio. File hashes detect accidental/tampered artifacts, not an intentionally compromised runtime.
