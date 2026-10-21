import json
from pathlib import Path

import pytest

from mgsf.musmus_bgm import MusMusIntakeError, run_musmus_intake


def _manifest(tmp_path: Path, **track_changes):
    root = tmp_path / "game"
    root.mkdir(exist_ok=True)
    track = {
        "id": "town-theme",
        "title": "Human-curated placeholder",
        "source_page": "https://musmus.main.jp/",
        "audio_path": "assets/audio/town.ogg",
        "loop_mode": "intro",
        "selected_by_human": True,
        "license_reviewed": True,
    }
    track.update(track_changes)
    payload = {"schema_version": 1, "project": "Demo Game", "tracks": [track]}
    manifest = tmp_path / "musmus.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return root, manifest, payload


def _run(tmp_path, root, manifest):
    return run_musmus_intake(manifest, root, tmp_path / "evidence")


def test_missing_audio_stays_hold_and_produces_credit(tmp_path):
    root, manifest, _ = _manifest(tmp_path)
    out = _run(tmp_path, root, manifest)
    report = json.loads((out / "intake-report.json").read_text(encoding="utf-8"))
    assert report["release_gate"] == "HOLD"
    assert report["human_audio_review_required"] is True
    assert report["tracks"][0]["audio_present"] is False
    assert "OFFICIAL_AUDIO_NOT_PRESENT" in report["tracks"][0]["checks"]
    assert "LOOP_OFFSET_UNCONFIRMED" in report["tracks"][0]["checks"]
    assert "BGM: MusMus" in (out / "CREDITS-draft.txt").read_text(encoding="utf-8")
    assert "LOOPSTART" in (out / "ENGINE-NOTES.md").read_text(encoding="utf-8")


def test_audio_file_presence_does_not_claim_playback(tmp_path):
    root, manifest, _ = _manifest(tmp_path, loop_offset_seconds=4.5)
    audio = root / "assets/audio/town.ogg"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"not validated audio: do not decode")
    out = _run(tmp_path, root, manifest)
    report = json.loads((out / "intake-report.json").read_text(encoding="utf-8"))
    assert report["tracks"][0]["audio_present"] is True
    assert report["tracks"][0]["intake_state"] == "READY_FOR_MANUAL_PLAYBACK"
    assert report["release_gate"] == "HOLD"
    assert report["audio_decoded_or_modified"] is False
    assert audio.read_bytes() == b"not validated audio: do not decode"
    assert sorted(p.name for p in out.iterdir()) == [
        "CREDITS-draft.txt", "ENGINE-NOTES.md", "intake-report.json"
    ]


def test_unselected_track_never_gets_final_credit_claim(tmp_path):
    root, manifest, _ = _manifest(tmp_path, selected_by_human=False, license_reviewed=False)
    out = _run(tmp_path, root, manifest)
    credits = (out / "CREDITS-draft.txt").read_text(encoding="utf-8")
    assert "Human-curated placeholder" not in credits
    report = json.loads((out / "intake-report.json").read_text(encoding="utf-8"))
    assert "LICENSE_REVIEW_PENDING" in report["tracks"][0]["checks"]
    assert "HUMAN_SELECTION_PENDING" in report["tracks"][0]["checks"]


@pytest.mark.parametrize("unsafe", ["../escape.ogg", "/etc/private.ogg", "assets/audio/music.wav", "C:\\\\temp\\\\evil.ogg"])
def test_reject_unsafe_or_nonmusic_paths(tmp_path, unsafe):
    root, manifest, _ = _manifest(tmp_path, audio_path=unsafe)
    with pytest.raises(MusMusIntakeError):
        _run(tmp_path, root, manifest)


def test_reject_symlink_audio(tmp_path):
    root, manifest, _ = _manifest(tmp_path)
    external = tmp_path / "outside.ogg"
    external.write_bytes(b"test")
    destination = root / "assets/audio/town.ogg"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(external)
    with pytest.raises(MusMusIntakeError, match="symbolic"):
        _run(tmp_path, root, manifest)


@pytest.mark.parametrize(
    "url",
    [
        "https://musmus.main.jp.attacker.example/song",
        "http://musmus.main.jp/",
        "https://evil.example/",
        "https://musmus.main.jp/music/file.ogg",
    ],
)
def test_only_official_musmus_webpages(tmp_path, url):
    root, manifest, _ = _manifest(tmp_path, source_page=url)
    with pytest.raises(MusMusIntakeError):
        _run(tmp_path, root, manifest)


def test_duplicate_track_id_rejected(tmp_path):
    root, manifest, payload = _manifest(tmp_path)
    payload["tracks"].append(dict(payload["tracks"][0]))
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MusMusIntakeError, match="duplicate"):
        _run(tmp_path, root, manifest)


@pytest.mark.parametrize("bad", [True, "5", float("nan"), -1, 0])
def test_invalid_intro_offsets_rejected(tmp_path, bad):
    root, manifest, _ = _manifest(tmp_path, loop_offset_seconds=bad)
    with pytest.raises(MusMusIntakeError):
        _run(tmp_path, root, manifest)


def test_full_loop_has_no_intro_offset(tmp_path):
    root, manifest, _ = _manifest(tmp_path, loop_mode="full", loop_offset_seconds=1)
    with pytest.raises(MusMusIntakeError):
        _run(tmp_path, root, manifest)


def test_reject_wrong_schema(tmp_path):
    root, manifest, payload = _manifest(tmp_path)
    payload["schema_version"] = 2
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MusMusIntakeError, match="schema_version"):
        _run(tmp_path, root, manifest)
