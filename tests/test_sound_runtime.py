import io
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest
import wave
import zipfile

from mgsf.sound_identity import run_sound_identity
from mgsf.sound_runtime import (
    SoundRuntimeError, load_verified_audio_map, run_sound_runtime, verify_engine_evidence,
)


def tone():
    result = io.BytesIO()
    with wave.open(result, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"".join(int(8000 * math.sin(2 * math.pi * i / 100)).to_bytes(2, "little", signed=True)
                             for i in range(8000)))
    return result.getvalue()


class SoundRuntimeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "game"
        self.project.mkdir()
        (self.project / "project.godot").write_text('[application]\nconfig/name="MGSF Sound CI"\n', encoding="utf-8")
        src = self.root / "export.zip"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("title.wav", tone())
        self.out = self.root / "evidence"
        run_sound_identity(src, self.project, self.root / "import.json", apply=True)
        self.tracks = load_verified_audio_map(self.project)

    def test_hashed_godot_map(self):
        self.assertEqual(len(self.tracks), 1)
        self.assertTrue(self.tracks[0]["path"].endswith(".wav"))

    def test_mutated_wav_rejected(self):
        Path(self.tracks[0]["path"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(SoundRuntimeError, "checksum"):
            load_verified_audio_map(self.project)

    def test_symlink_asset_rejected(self):
        asset = Path(self.tracks[0]["path"])
        target = self.root / "outside.wav"
        asset.rename(target)
        asset.symlink_to(target)
        with self.assertRaisesRegex(SoundRuntimeError, "symlink"):
            load_verified_audio_map(self.project)

    def test_escape_destination_rejected(self):
        map_path = self.project / "audio/mgsf_sound_identity/sound_map.json"
        data = json.loads(map_path.read_text())
        data["tracks"][0]["destination"] = "res://../../secret.wav"
        map_path.write_text(json.dumps(data))
        with self.assertRaisesRegex(SoundRuntimeError, "destination"):
            load_verified_audio_map(self.project)

    def test_duplicate_rejected(self):
        map_path = self.project / "audio/mgsf_sound_identity/sound_map.json"
        data = json.loads(map_path.read_text())
        data["tracks"].append(data["tracks"][0])
        map_path.write_text(json.dumps(data))
        with self.assertRaisesRegex(SoundRuntimeError, "duplicate"):
            load_verified_audio_map(self.project)

    def test_cross_check_rejects_wrong_source(self):
        fake = {"schema": "mgsf.sound_identity.engine_state.v0.3", "driver": "Dummy",
                "engine_version": "4.7.2", "engine_checks_passed": True,
                "observations": [{"sha256": "0" * 64, "switched_after": "",
                                  "load_ok": True, "started": True, "stopped": True,
                                  "loop_configured": True, "timestamp_ms": 1}]}
        self.assertIn("wrong_source_or_transition_0", verify_engine_evidence(fake, self.tracks))

    def test_false_success_is_rejected(self):
        fake = {"schema": "mgsf.sound_identity.engine_state.v0.3", "driver": "Dummy",
                "engine_version": "4.7.2", "engine_checks_passed": True,
                "observations": [{"sha256": self.tracks[0]["sha256"], "switched_after": "",
                                  "load_ok": True, "started": False, "stopped": True,
                                  "loop_configured": True, "timestamp_ms": 1}]}
        self.assertIn("play_state_not_confirmed_0", verify_engine_evidence(fake, self.tracks))

    def test_refuse_project_output_even_without_running_engine(self):
        with self.assertRaisesRegex(SoundRuntimeError, "outside"):
            run_sound_runtime(self.project, "not-a-godot", self.project / "evidence")

    def _engine_stub(self, command, *, cwd, env, capture_output, text, errors, timeout):
        input_spec = json.loads(Path(env["MGSF_SOUND_PROBE_SPEC"]).read_text())
        observations = []
        previous = ""
        for track in input_spec["tracks"]:
            observations.append({"sha256": track["sha256"], "switched_after": previous,
                                 "load_ok": True, "started": True, "stopped": True,
                                 "loop_configured": True, "timestamp_ms": 100})
            previous = track["sha256"]
        Path(input_spec["result_path"]).write_text(json.dumps({
            "schema": "mgsf.sound_identity.engine_state.v0.3",
            "driver": "Dummy", "engine_version": "4.7.2",
            "observations": observations, "engine_checks_passed": True,
        }))
        return SimpleNamespace(returncode=0, stdout="MGSF_SOUND_ENGINE_STATE_OK\n", stderr="")

    def test_engine_stub_only_state_pass_with_promotion_hold(self):
        with patch("mgsf.sound_runtime.shutil.which", return_value="/fake/godot"):
            with patch("mgsf.sound_runtime.subprocess.run", side_effect=self._engine_stub):
                result = run_sound_runtime(self.project, "godot", self.out, fixture=True)
        self.assertEqual(result["technical_status"], "PASS")
        self.assertEqual(result["promotion_gate"], "HOLD")
        self.assertFalse(result["observed_audio"])
        self.assertEqual(result["evidence_class"], "synthetic_wav_real_engine_probe")
        self.assertTrue((self.out / "evaluation.json").is_file())

    def test_engine_failure_holds_with_evidence(self):
        with patch("mgsf.sound_runtime.shutil.which", return_value="/fake/godot"):
            with patch("mgsf.sound_runtime.subprocess.run", return_value=SimpleNamespace(
                returncode=3, stdout="", stderr="SCRIPT ERROR: broken")):
                result = run_sound_runtime(self.project, "godot", self.out, fixture=True)
        self.assertEqual(result["technical_status"], "FAIL")
        self.assertEqual(result["promotion_gate"], "HOLD")
        self.assertIn("engine_process_failed_or_timed_out", result["errors"])

    @unittest.skipUnless(os.environ.get("MGSF_GODOT_EXECUTABLE"), "real Godot only in CI with explicit binary")
    def test_real_headless_godot_state_probe(self):
        result = run_sound_runtime(self.project, os.environ["MGSF_GODOT_EXECUTABLE"],
                                   self.out, fixture=True)
        self.assertEqual(result["technical_status"], "PASS",
                         (self.out / "godot-run.json").read_text())
        self.assertEqual(result["engine_driver"], "Dummy")
        self.assertEqual(result["promotion_gate"], "HOLD")
        self.assertFalse(result["observed_audio"])


if __name__ == "__main__":
    unittest.main()
