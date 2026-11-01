# MGSF Sound Identity Lab M0.2 (incubation)

Offline, opt-in WAV evaluation and safe import for Godot 4. Uses Python's standard library, no network, no API keys, no reverse engineering of AMIX. Input is a ZIP explicitly exported by its user; MIDI/JSON are provenance only.

## Contract

- Input: a bounded ZIP of PCM WAV and optional MIDI/JSON, a Godot 4 project with `project.godot`, optional versioned scene map.
- Output: JSON technical inspection report, original WAV SHA-256 and archive SHA-256, Godot `res://` audio destination plan, technical PASS/REVIEW/HOLD.
- Default behavior: dry run. **Never writes to Godot without `--apply`**.
- Apply: copy validated WAV bytes into `res://audio/mgsf_sound_identity/` using collision-resistant names and create `sound_map.json`. No existing files or scenes are overwritten.
- Loop requests are **metadata only**. Configure and test loop playback inside Godot manually. This tool does not edit `.import` files or scenes.
- Any invalid/silent WAV blocks apply. Potential clipping or raw boundary mismatch requires `--allow-review` plus a real human listening check.
- `promotion_gate` always `HOLD` at M0.2. Passing static checks never proves in-game sound quality, production license compliance, or actual gameplay evidence.

## CLI

```bash
mgsf sound-identity path/to/export.zip path/to/godot-project --out evidence/sound-identity/report.json
mgsf sound-identity path/to/export.zip path/to/godot-project --scene-map path/to/scene-map.json --apply --out evidence/sound-identity/applied.json
# For REVIEW inputs only, after human listening and approval:
mgsf sound-identity path/to/export.zip path/to/godot-project --apply --allow-review
```

Example `scene-map.json`:

```json
{
  "schema": "mgsf.sound_identity.scene_map.v0.2",
  "scenes": {"res://scenes/main.tscn": "music/title.wav"},
  "loops": ["music/title.wav"]
}
```

Scanned archive paths are matched exactly by name. `scene_tracks` and `tracks` in the report provide `res://` paths for manual wiring in Godot; the program intentionally does not rewrite gameplay scenes.

## Safety and evidence boundaries

- File count <= 200; archive and total uncompressed bytes <= 100 MiB; each entry <= 30 MiB.
- Reject traversal, drive/ADS, hidden, reserved device names, repeated case-folded paths, and Unix ZIP symlinks.
- Reject unsupported WAV and truncated frame data. Peak, RMS, silence and sample-end checks are **technical heuristics**, not perceptual quality scores.
- Copy only under a dedicated Godot audio folder. Existing paths and symlinks refuse apply; created files are removed if copy fails mid-operation.
- `.mid`, `.midi`, `.json` are only hashed; the tool makes no claims to parse their source-specific structure.
- This release has only generated fixture coverage; no verified AMIX export, Godot live import, Windows test, real-project dogfood, or license legal review yet. Remains incubation.

## Acceptance for next milestone

1. Replay a genuine user-exported ZIP (not a synthetic fixture) and save hashes and review notes.
2. Import a PASS track in a real Godot 4 project, confirm playback and loop behavior by engine evidence.
3. Run CI tests on Ubuntu/Windows and preserve results.
4. Independently review license metadata, usability, false positive rate and failure modes.
5. Gate any promotion decision on real-project evidence, never fixture PASS alone.
