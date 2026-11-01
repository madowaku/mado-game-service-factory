import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave
import zipfile

from mgsf.sound_identity import run_sound_identity
from mgsf.sound_director import (
    SoundDirectorError, _midi_motifs, run_sound_director,
)


def wav(hz=200, broken=False):
    out = io.BytesIO()
    samples = [int(10000 * math.sin(2 * math.pi * hz * i / 16000))
               for i in range(16000)]
    if broken:
        samples[-1] = 25000
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"".join(int(v).to_bytes(2, "little", signed=True) for v in samples))
    return out.getvalue()


def vlq(value):
    bits = [value & 127]
    value >>= 7
    while value:
        bits.append(0x80 | (value & 127))
        value >>= 7
    return bytes(reversed(bits))


def midi(notes, transpose=0, *, running=False, corrupt=False):
    events = bytearray()
    for i, pitch in enumerate(notes):
        # Each note starts after preceding note-off, using 120 PPQ.
        events.extend(b"\x00" + (b"\x90" if i == 0 or not running else b""))
        events.extend(bytes([(pitch + transpose) % 128, 90]))
        events.extend(vlq(120) + bytes([0x80, (pitch + transpose) % 128, 0]))
    events.extend(b"\x00\xff\x2f\x00")
    if corrupt:
        events = events[:-2]
    return (b"MThd" + (6).to_bytes(4, "big") + b"\x00\x00\x00\x01\x01\xe0" +
            b"MTrk" + len(events).to_bytes(4, "big") + events)


class SoundDirectorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.project = self.root / "godot"
        self.project.mkdir()
        (self.project / "project.godot").write_text('[application]\n', encoding="utf-8")
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        archive = self.inputs / "audio.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("title.wav", wav(200))
            bundle.writestr("battle.wav", wav(300))
        scene_map = self.inputs / "scene-map.json"
        scene_map.write_text(json.dumps({
            "schema": "mgsf.sound_identity.scene_map.v0.2",
            "scenes": {},
            "loops": ["title.wav"]
        }), encoding="utf-8")
        run_sound_identity(archive, self.project, self.root / "import.json",
                           scene_map, apply=True)
        tracks = json.loads(
            (self.project / "audio/mgsf_sound_identity/sound_map.json").read_text()
        )["tracks"]
        self.title = next(x for x in tracks if x["source"] == "title.wav")
        self.battle = next(x for x in tracks if x["source"] == "battle.wav")
        self.m1 = self.inputs / "title.mid"
        self.m2 = self.inputs / "battle.mid"
        self.m1.write_bytes(midi([60, 62, 64, 65, 67, 69, 71], running=True))
        self.m2.write_bytes(midi([60, 62, 64, 65, 67, 69, 71], transpose=12))
        self.brief_path = self.inputs / "brief.json"
        self.brief = {"schema": "mgsf.sound_identity.director_brief.v0.5", "tracks": [
            {"role": "title", "destination": self.title["destination"],
             "scene": "res://scenes/title.tscn", "midi": "title.mid"},
            {"role": "battle", "destination": self.battle["destination"],
             "scene": "res://scenes/battle.tscn", "midi": "battle.mid"},
        ]}
        self.save()
        self.out = self.root / "evidence"

    def save(self):
        self.brief_path.write_text(json.dumps(self.brief), encoding="utf-8")

    def run_director(self, **kwargs):
        return run_sound_director(self.project, self.brief_path, self.out, **kwargs)

    def test_transposed_motif_matches_but_does_not_promote(self):
        result = self.run_director(fixture=True)
        self.assertEqual(result["motif_comparisons"][0]["pattern_overlap"], 1.0)
        self.assertEqual(result["track_count"], 2)
        self.assertEqual(result["promotion_gate"], "HOLD")
        self.assertEqual(result["technical_status"], "REVIEW")
        self.assertFalse(result["human_review"]["provided"])
        self.assertFalse(result["tracks"][0]["scene_binding_verified"])
        self.assertTrue((self.out / "review-template.json").is_file())
        self.assertTrue((self.out / "review-queue.json").is_file())

    def test_missing_midi_is_unknown_not_zero(self):
        del self.brief["tracks"][1]["midi"]
        self.save()
        report = self.run_director()
        self.assertIsNone(report["motif_comparisons"][0]["pattern_overlap"])
        self.assertIn("midi_not_supplied", report["flags"])

    def test_weak_interval_overlap_is_only_review_flag(self):
        self.m2.write_bytes(midi([60, 69, 62, 81, 67, 85, 70]))
        report = self.run_director()
        self.assertEqual(report["motif_comparisons"][0]["pattern_overlap"], 0)
        self.assertIn("low_interval_pattern_overlap_review", report["flags"])
        self.assertEqual(report["promotion_gate"], "HOLD")

    def test_requested_loop_has_boundary_metric(self):
        report = self.run_director()
        self.assertIsNotNone(report["tracks"][0]["loop_seam_heuristic"])
        self.assertIsNone(report["tracks"][1]["loop_seam_heuristic"])

    def test_loop_boundary_jump_is_review_not_audibility_proof(self):
        # Fresh project with a non-periodic seam.
        archive = self.inputs / "broken.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("broken.wav", wav(200, broken=True))
        different = self.root / "other-project"
        different.mkdir()
        (different / "project.godot").write_text('[application]\n')
        maps = self.inputs / "broken-map.json"
        maps.write_text(json.dumps({"schema": "mgsf.sound_identity.scene_map.v0.2",
                                    "scenes": {}, "loops": ["broken.wav"]}))
        run_sound_identity(archive, different, self.root / "broken-report.json",
                           maps, apply=True, allow_review=True)
        record = json.loads((different / "audio/mgsf_sound_identity/sound_map.json").read_text())["tracks"][0]
        b = self.inputs / "broken-brief.json"
        b.write_text(json.dumps({"schema": "mgsf.sound_identity.director_brief.v0.5",
                                 "tracks": [{"role": "menu", "destination": record["destination"],
                                             "scene": "res://menu.tscn"}]}))
        report = run_sound_director(different, b, self.out)
        self.assertIn("possible_loop_boundary_click", report["flags"])
        self.assertTrue(report["tracks"][0]["loop_seam_heuristic"]["possible_click_risk"])

    def test_invalid_midi_header_rejected(self):
        self.m1.write_bytes(b"not midi")
        with self.assertRaisesRegex(SoundDirectorError, "MIDI header"):
            self.run_director()

    def test_truncated_midi_rejected(self):
        self.m1.write_bytes(midi([60, 64, 67], corrupt=True))
        with self.assertRaises(SoundDirectorError):
            self.run_director()

    def test_midi_traversal_rejected(self):
        self.brief["tracks"][0]["midi"] = "../secret.mid"
        self.save()
        with self.assertRaisesRegex(SoundDirectorError, "traversal"):
            self.run_director()

    def test_midi_symlink_rejected(self):
        target = self.root / "external.mid"
        target.write_bytes(self.m1.read_bytes())
        self.m1.unlink()
        self.m1.symlink_to(target)
        with self.assertRaisesRegex(SoundDirectorError, "symlink"):
            self.run_director()

    def test_unbound_destination_rejected(self):
        self.brief["tracks"][1]["destination"] = "res://other.wav"
        self.save()
        with self.assertRaisesRegex(SoundDirectorError, "unknown or duplicate"):
            self.run_director()

    def test_duplicate_destination_rejected(self):
        self.brief["tracks"][1]["destination"] = self.title["destination"]
        self.save()
        with self.assertRaisesRegex(SoundDirectorError, "unknown or duplicate"):
            self.run_director()

    def test_unknown_role_rejected(self):
        self.brief["tracks"][0]["role"] = "ultimate_mood"
        self.save()
        with self.assertRaisesRegex(SoundDirectorError, "role"):
            self.run_director()

    def test_scene_traversal_rejected(self):
        self.brief["tracks"][0]["scene"] = "res://../secret.tscn"
        self.save()
        with self.assertRaisesRegex(SoundDirectorError, "scene"):
            self.run_director()

    def test_audio_checksum_tamper_rejected_before_director(self):
        asset = self.project / self.title["destination"][6:]
        asset.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.run_director()

    def test_human_review_claims_not_automatic_promotion(self):
        review = self.inputs / "review.json"
        review.write_text(json.dumps({"schema": "mgsf.sound_identity.human_review.v0.5",
                                       "reviewer": "local volunteer",
                                       "assessments": [{
                                           "destination": d, "scene_fit": 4, "motif_recognizability": 3,
                                           "loop_naturalness": 5, "mix_balance": 3, "notes": "Manual sample"
                                       } for d in (self.title["destination"], self.battle["destination"])]}))
        report = self.run_director(review=review)
        self.assertTrue(report["human_review"]["complete"])
        self.assertEqual(report["human_review"]["covered_tracks"], 2)
        self.assertEqual(report["promotion_gate"], "HOLD")

    def test_invalid_review_score_rejected(self):
        review = self.inputs / "bad-review.json"
        review.write_text(json.dumps({"schema": "mgsf.sound_identity.human_review.v0.5",
                                       "reviewer": "human", "assessments": [{
                                           "destination": self.title["destination"], "scene_fit": 6,
                                           "motif_recognizability": 4, "loop_naturalness": 3,
                                           "mix_balance": 3, "notes": "text"}]}))
        with self.assertRaisesRegex(SoundDirectorError, "review scores"):
            self.run_director(review=review)

    def test_evidence_location_must_be_outside_project(self):
        with self.assertRaisesRegex(SoundDirectorError, "outside"):
            run_sound_director(self.project, self.brief_path, self.project / "evidence")

    def test_midi_note_onsets_running_status(self):
        info = _midi_motifs(self.m1)
        self.assertEqual(info["note_onsets"], 7)
        self.assertGreater(info["pattern_count"], 0)


if __name__ == "__main__":
    unittest.main()
