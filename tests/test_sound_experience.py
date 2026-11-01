"""Sound Experience M0.6 deterministic fixture tests. Never real speaker evidence."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from mgsf.sound_experience import SoundExperienceError, run_sound_experience


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "input"
        self.input.mkdir()
        self.wav = self.input / "master-bus.wav"
        self.manifest = self.input / "capture-manifest.json"
        self.output = self.root / "evidence"
        self.make_audio()
        self.data = {"schema": "mgsf.sound_identity.capture_manifest.v0.6",
                     "origin": "synthetic_fixture", "audio_driver": "Dummy",
                     "consent": True, "sample_rate": 16000, "channels": 2,
                     "sample_count": 32000, "discarded_frames": 0,
                     "capture_started_ticks_usec": 1000000,
                     "capture_ended_ticks_usec": 3000000,
                     "markers": [{"marker_id": "intro", "kind": "start", "ticks_usec": 1500000},
                                 {"marker_id": "repeat", "kind": "loop", "ticks_usec": 2000000}],
                     "recording_sha256": self.sha()}
        self.save()

    def make_audio(self, silent=False, clipped=False, discontinuity=False):
        frames = []
        for i in range(32000):
            if silent:
                v = 0
            elif clipped:
                v = 32767
            else:
                v = int(9000 * math.sin(2 * math.pi * i / 80))
            if discontinuity and i == 16000:
                v = -32768
            frames.append(v.to_bytes(2, "little", signed=True) * 2)
        with wave.open(str(self.wav), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(b"".join(frames))

    def sha(self):
        return hashlib.sha256(self.wav.read_bytes()).hexdigest()

    def save(self):
        self.manifest.write_text(json.dumps(self.data), encoding="utf-8")

    def analyze(self, **kwargs):
        return run_sound_experience(self.manifest, self.wav, self.output, fixture=True, **kwargs)

    def test_synthetic_valid_never_promoted(self):
        report = self.analyze()
        self.assertEqual(report["promotion_gate"], "HOLD")
        self.assertFalse(report["actual_speaker_output_verified"])
        self.assertEqual(report["audio"]["sample_count"], 32000)
        self.assertEqual(report["marker_count"], 2)
        self.assertEqual(report["capture_duration_drift_ms"], 0)
        self.assertTrue((self.output / "evaluation.json").is_file())

    def test_fixture_cannot_pass_as_real(self):
        with self.assertRaisesRegex(SoundExperienceError, "requires --fixture"):
            run_sound_experience(self.manifest, self.wav, self.output)

    def test_invalid_digest_rejected(self):
        self.data["recording_sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(SoundExperienceError, "hash mismatch"):
            self.analyze()

    def test_missing_consent_rejected(self):
        self.data["consent"] = False
        self.save()
        with self.assertRaisesRegex(SoundExperienceError, "consent"):
            self.analyze()

    def test_sample_count_mismatch_rejected(self):
        self.data["sample_count"] = 32001
        self.save()
        with self.assertRaisesRegex(SoundExperienceError, "sample_count"):
            self.analyze()

    def test_silence_is_flagged(self):
        self.make_audio(silent=True)
        self.data["recording_sha256"] = self.sha()
        self.save()
        report = self.analyze()
        self.assertIn("long_silence_in_recording_review", report["flags"])

    def test_clipping_is_flagged(self):
        self.make_audio(clipped=True)
        self.data["recording_sha256"] = self.sha()
        self.save()
        report = self.analyze()
        self.assertIn("possible_clipping_in_capture", report["flags"])

    def test_loop_discontinuity_is_only_heuristic(self):
        self.make_audio(discontinuity=True)
        self.data["recording_sha256"] = self.sha()
        self.save()
        report = self.analyze()
        self.assertIn("possible_loop_transition_click", report["flags"])
        self.assertEqual(report["promotion_gate"], "HOLD")

    def test_marker_beyond_samples_is_flagged(self):
        self.data["markers"][1]["ticks_usec"] = 3_000_000
        self.save()
        report = self.analyze()
        self.assertIn("audio_event_marker_outside_recording", report["flags"])
        self.assertEqual(report["promotion_gate"], "HOLD")

    def test_overflow_flag(self):
        self.data["discarded_frames"] = 10
        self.save()
        self.assertIn("audio_capture_ring_buffer_overflow", self.analyze()["flags"])

    def test_unsynced_duration_flag(self):
        self.data["capture_ended_ticks_usec"] = 3500000
        self.save()
        self.assertIn("capture_clock_duration_mismatch", self.analyze()["flags"])

    def test_nonmonotonic_marker_rejected(self):
        self.data["markers"][1]["ticks_usec"] = 1400000
        self.save()
        with self.assertRaisesRegex(SoundExperienceError, "monotonic"):
            self.analyze()

    def test_marker_outside_session_rejected(self):
        self.data["markers"][0]["ticks_usec"] = 900000
        self.save()
        with self.assertRaisesRegex(SoundExperienceError, "monotonic"):
            self.analyze()

    def test_duplicate_marker_rejected(self):
        self.data["markers"][1]["marker_id"] = "intro"
        self.save()
        with self.assertRaisesRegex(SoundExperienceError, "duplicate"):
            self.analyze()

    def test_input_with_dummy_driver_cannot_claim_audio(self):
        self.data["origin"] = "godot_master_bus_audioeffectcapture"
        self.save()
        report = run_sound_experience(self.manifest, self.wav, self.output)
        self.assertIn("dummy_audio_driver_not_real_output", report["flags"])
        self.assertFalse(report["actual_speaker_output_verified"])

    def test_external_loopback_claim_is_unverified(self):
        self.data["origin"] = "external_loopback"
        self.data["audio_driver"] = "WASAPI"
        self.save()
        report = run_sound_experience(self.manifest, self.wav, self.output)
        self.assertIn("external_loopback_provenance_unverified", report["flags"])
        self.assertEqual(report["promotion_gate"], "HOLD")

    def test_output_cannot_write_inside_input(self):
        with self.assertRaisesRegex(SoundExperienceError, "outside"):
            run_sound_experience(self.manifest, self.wav, self.input / "evidence", fixture=True)

    def test_symlink_manifest_rejected(self):
        real = self.root / "real.json"
        self.manifest.rename(real)
        self.manifest.symlink_to(real)
        with self.assertRaisesRegex(SoundExperienceError, "symlinked"):
            self.analyze()

    def test_missing_wav_rejected(self):
        self.wav.unlink()
        with self.assertRaisesRegex(SoundExperienceError, "missing"):
            self.analyze()


if __name__ == "__main__":
    unittest.main()
