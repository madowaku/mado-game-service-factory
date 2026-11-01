# MGSF Sound Identity Lab M0.4: Gameplay x Audio Timeline (incubation)

M0.4 correlates source-identified WAV tracks, declared audio callbacks and MGSF gameplay-capture timeline events. It optionally inspects bounded **user-supplied PCM WAV** windows for silence/clipping. It does **not** create a recorder, inject into gameplay, prove clock synchronization, or verify a physical audio output device. All promotion decisions stay **HOLD**.

## Run

```bash
mgsf sound-timeline path/to/capture-input path/to/godot-project audio-timeline.json \
  --recording path/to/loopback.wav --output-root evidence/sound-timeline

# Synthetic/reconstruction case:
mgsf sound-timeline fixtures/gameplay-capture/vertical-slice-reconstruction \
  path/to/fixture-godot audio-timeline.json \
  --recording synthetic-tone.wav --fixture
```

Inputs: the MGSF `capture.json`, `timeline.jsonl` and referenced media; M0.2 `sound_map.json` with hash-matched imported WAV; separate JSON audio event trace sharing **declared** `capture_timeline_ms` clock; optionally a PCM WAV recording. Events must have stable IDs and refer to a real capture timeline event in the same capture/session. Each event must fall within 0..250ms *after* its linked capture event, use a known SHA-256 track, be timestamp-monotonic, and obey start -> switch -> stop rules.

Sample audio trace:

```json
{
  "schema": "mgsf.sound_identity.audio_timeline.v0.4",
  "capture_id": "vertical-slice-c6-reconstruction",
  "session_id": "capture-001",
  "clock": "capture_timeline_ms",
  "recording_start_ms": 0,
  "events": [
    {"event_id": "sound-1", "kind": "start", "at_ms": 1420, "capture_event_id": "capture-event-002", "track_sha256": "REPLACE_WITH_REAL_64_HEX_WAV_SHA256"},
    {"event_id": "sound-2", "kind": "stop", "at_ms": 1820, "capture_event_id": "capture-event-004", "track_sha256": "SAME_SHA256"}
  ]
}
```

`recording_start_ms` declares the recording's time-zero on the same timeline; no independent synchronization check exists. PCM inspection uses a 60..200ms window after each event and calculates simple RMS, peak, possible silence/clipping. A tone heard elsewhere or audible quality can never be inferred from these numbers. Stop-event windows are also inspected, but silence following stop is not judged automatically. False positives/negatives are expected.

## Outputs

- `event-links.json`: matched gameplay event, WAV hash and **reported** timestamp delta for every audio event
- `evaluation.json`: source evidence class, recording provenance label `supplied_pcm_recording_unverified_source`, optional waveform metadata/heuristics, SHA-256 of input trace/capture manifest/timeline, flags and limitations, always `promotion_gate=HOLD`.
- No copying or uploading of user WAV by default; user-owned inputs remain at original paths. CI's generated tone is explicitly `synthetic-tone-NOT-recorded-from-godot.wav`.

A `technical_status=PASS` indicates only consistent assertions and absence of heuristically detected flags; it is **not** audio proof. A reconstructed capture, missing recording, or synthetic flag results in REVIEW. The workflow never conflates claims of callback timing, file provenance, or Godot Dummy state with independently recorded audio.

## Future promotion requirements

1. Genuine in-game instrumentation writes its event IDs and timestamps from the same monotonic clock used by gameplay-capture.
2. Establish measured shared-clock sync/offset/uncertainty, with an audit trail.
3. Obtain non-Dummy loopback/hardware recording with verifiable runtime and capture provenance.
4. Analyze gaps, loop seams, acoustic latency and actual game audio routes under multiple environments.
5. Have a human listen, confirm licensing and approve release. Keep all fixture-only evidence on HOLD.
