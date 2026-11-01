import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave
import zipfile

from mgsf.sound_identity import run_sound_identity
from mgsf.sound_timeline import SoundTimelineError, run_sound_timeline


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/gameplay-capture/vertical-slice-reconstruction"


def pcm(tone: bool = True, *, clipping: bool = False, duration: float = 2.5) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        amplitude = 32767 if clipping else (9000 if tone else 0)
        f.writeframes(b"".join(
            int(amplitude * math.sin(2 * math.pi * 200 * i / 16000)).to_bytes(2, "little", signed=True)
            for i in range(int(duration * 16000))
        ))
    return out.getvalue()


class TimelineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "godot"
        self.project.mkdir()
        (self.project / "project.godot").write_text('[application]\n')
        export = self.root / "export.zip"
        with zipfile.ZipFile(export, "w") as z:
            z.writestr("title.wav", pcm(duration=0.5))
            z.writestr("battle.wav", pcm(duration=0.5).replace(b"unused", b"unused"))
        run_sound_identity(export, self.project, self.root / "import.json", apply=True)
        records = json.loads((self.project / "audio/mgsf_sound_identity/sound_map.json").read_text())["tracks"]
        self.hash = records[0]["sha256"]
        self.trace = self.root / "audio-events.json"
        self.out = self.root / "evaluation"
        self.data = {
            "schema": "mgsf.sound_identity.audio_timeline.v0.4",
            "capture_id": "vertical-slice-c6-reconstruction", "session_id": "capture-001",
            "clock": "capture_timeline_ms", "recording_start_ms": 0,
            "events": [
                {"event_id": "sound-1", "kind": "start", "at_ms": 1420, "track_sha256": self.hash,
                 "capture_event_id": "capture-event-002"},
                {"event_id": "sound-2", "kind": "switch", "at_ms": 1615, "track_sha256": self.hash,
                 "capture_event_id": "capture-event-003"},
                {"event_id": "sound-3", "kind": "stop", "at_ms": 1825, "track_sha256": self.hash,
                 "capture_event_id": "capture-event-004"},
            ],
        }
        self.save_trace()

    def save_trace(self):
        self.trace.write_text(json.dumps(self.data), encoding="utf-8")

    def evaluate(self, recording=None, fixture=True):
        return run_sound_timeline(FIXTURE, self.project, self.trace, self.out,
                                  recording=recording, fixture=fixture)

    def test_fixture_timeline_links_and_holds(self):
        result = self.evaluate()
        self.assertEqual(result["promotion_gate"], "HOLD")
        self.assertEqual(result["event_count"], 3)
        self.assertEqual(result["technical_status"], "REVIEW")
        self.assertIn("capture_not_direct_gameplay", result["flags"])
        links = json.loads((self.out / "event-links.json").read_text())["linked_events"]
        self.assertEqual([x["reported_delta_ms"] for x in links], [20, 15, 25])

    def test_pcm_recording_window_is_heuristic_only(self):
        wav = self.root / "recording.wav"
        wav.write_bytes(pcm())
        result = self.evaluate(wav)
        self.assertTrue(result["recording"]["event_windows"][0]["window_available"])
        self.assertGreater(result["recording"]["event_windows"][0]["rms"], 0.05)
        self.assertEqual(result["audio_evidence_class"], "supplied_pcm_recording_unverified_source")
        self.assertEqual(result["promotion_gate"], "HOLD")

    def test_silent_recording_flags(self):
        wav = self.root / "recording.wav"
        wav.write_bytes(pcm(tone=False))
        result = self.evaluate(wav)
        self.assertIn("possible_silence_near_audio_event", result["flags"])

    def test_recording_out_of_range(self):
        wav = self.root / "recording.wav"
        wav.write_bytes(pcm(duration=0.5))
        result = self.evaluate(wav)
        self.assertIn("recording_window_out_of_range", result["flags"])

    def test_invalid_recording_rejected(self):
        wav = self.root / "bad.wav"
        wav.write_bytes(b"bad")
        with self.assertRaises(SoundTimelineError):
            self.evaluate(wav)

    def test_wrong_capture_id(self):
        self.data["capture_id"] = "unrelated"
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "identity mismatch"):
            self.evaluate()

    def test_wrong_clock(self):
        self.data["clock"] = "wallclock"
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "clock"):
            self.evaluate()

    def test_unknown_capture_event(self):
        self.data["events"][0]["capture_event_id"] = "fake"
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "unknown capture event"):
            self.evaluate()

    def test_unknown_sound_hash(self):
        self.data["events"][1]["track_sha256"] = "0" * 64
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "unknown WAV"):
            self.evaluate()

    def test_non_monotonic_timestamp(self):
        self.data["events"][1]["at_ms"] = 1200
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "monotonic"):
            self.evaluate()

    def test_negative_delta(self):
        self.data["events"][0]["at_ms"] = 1399
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "correlation"):
            self.evaluate()

    def test_duplicate_id(self):
        self.data["events"][1]["event_id"] = "sound-1"
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "duplicate"):
            self.evaluate()

    def test_bad_transition(self):
        self.data["events"][0]["kind"] = "stop"
        self.save_trace()
        with self.assertRaisesRegex(SoundTimelineError, "stop without"):
            self.evaluate()

    def test_cannot_write_inside_godot_or_capture(self):
        with self.assertRaisesRegex(SoundTimelineError, "outside"):
            run_sound_timeline(FIXTURE, self.project, self.trace, self.project / "output")

    def test_no_recording_never_claims_audio(self):
        result = self.evaluate(fixture=False)
        self.assertEqual(result["audio_evidence_class"], "event_trace_only")
        self.assertIsNone(result["recording"])
        self.assertEqual(result["promotion_gate"], "HOLD")
