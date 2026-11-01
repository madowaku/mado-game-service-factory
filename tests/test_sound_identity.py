import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave
import zipfile

from mgsf.sound_identity import analyze_package, run_sound_identity


def wav(values):
    out = io.BytesIO()
    with wave.open(out, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b''.join(int(v).to_bytes(2, 'little', signed=True) for v in values))
    return out.getvalue()


TONE = wav([int(12000 * math.sin(2 * math.pi * j / 80)) for j in range(16000)])


class SoundIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'godot'
        self.project.mkdir()
        (self.project / 'project.godot').write_text('[application]\\n')
        self.archive = self.root / 'music.zip'
        self.report = self.root / 'report.json'

    def make_zip(self, files):
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, data in files.items():
                z.writestr(name, data)

    def test_dry_run_never_changes_godot(self):
        self.make_zip({'music/title.wav': TONE})
        result = run_sound_identity(self.archive, self.project, self.report)
        self.assertEqual(result['technical_status'], 'PASS')
        self.assertEqual(result['promotion_gate'], 'HOLD')
        self.assertFalse(result['applied'])
        self.assertFalse((self.project / 'audio').exists())
        self.assertEqual(json.loads(self.report.read_text())['archive_sha256'], result['archive_sha256'])

    def test_apply_copies_verified_wav_and_map(self):
        self.make_zip({'music/title.wav': TONE})
        mapfile = self.root / 'scenes.json'
        mapfile.write_text(json.dumps({'schema': 'mgsf.sound_identity.scene_map.v0.2',
                                       'scenes': {'res://scenes/main.tscn': 'music/title.wav'},
                                       'loops': ['music/title.wav']}))
        result = run_sound_identity(self.archive, self.project, self.report, mapfile, apply=True)
        self.assertTrue(result['applied'])
        self.assertEqual(len(result['tracks']), 1)
        self.assertTrue(result['tracks'][0]['loop_requested'])
        relative = result['tracks'][0]['destination'][6:]
        self.assertEqual((self.project / relative).read_bytes(), TONE)
        self.assertTrue((self.project / 'audio/mgsf_sound_identity/sound_map.json').is_file())
        self.assertEqual(result['scene_tracks']['res://scenes/main.tscn'], result['tracks'][0]['destination'])

    def test_will_not_overwrite(self):
        self.make_zip({'title.wav': TONE})
        run_sound_identity(self.archive, self.project, self.report, apply=True)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            run_sound_identity(self.archive, self.project, self.report, apply=True)

    def test_silence_holds_even_with_apply(self):
        self.make_zip({'silence.wav': wav([0] * 1000)})
        with self.assertRaisesRegex(ValueError, 'HOLD'):
            run_sound_identity(self.archive, self.project, self.report, apply=True)
        self.assertFalse((self.project / 'audio').exists())

    def test_unsupported_wav_holds(self):
        self.make_zip({'broken.wav': b'garbage'})
        result, _ = analyze_package(self.archive, self.project)
        self.assertEqual(result['technical_status'], 'HOLD')

    def test_path_traversal_rejected(self):
        self.make_zip({'../escape.wav': TONE})
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            analyze_package(self.archive, self.project)

    def test_duplicate_casefold_rejected(self):
        self.make_zip({'A.wav': TONE, 'a.wav': TONE})
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            analyze_package(self.archive, self.project)

    def test_missing_scene_track_rejected(self):
        self.make_zip({'title.wav': TONE})
        mapfile = self.root / 'bad.json'
        mapfile.write_text(json.dumps({'schema': 'mgsf.sound_identity.scene_map.v0.2',
                                       'scenes': {'res://main.tscn': 'missing.wav'}}))
        with self.assertRaisesRegex(ValueError, 'missing WAV'):
            analyze_package(self.archive, self.project, mapfile)

    def test_symlink_output_rejected(self):
        self.make_zip({'title.wav': TONE})
        (self.project / 'audio').symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            run_sound_identity(self.archive, self.project, self.report, apply=True)

    def test_non_godot_target_rejected(self):
        self.make_zip({'title.wav': TONE})
        with self.assertRaisesRegex(ValueError, 'Godot'):
            analyze_package(self.archive, self.root)


if __name__ == '__main__':
    unittest.main()
