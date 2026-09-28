from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from mgsf.gameplay_capture import (
    GameplayCaptureError,
    load_capture_session,
    run_gameplay_capture,
)


FIXTURE = Path("fixtures/gameplay-capture/vertical-slice-reconstruction")


def test_capture_fixture_is_explicitly_reconstructed() -> None:
    session = load_capture_session(FIXTURE)

    assert (
        session["source"]["evidence_class"]
        == "reconstructed_from_verified_state"
    )
    assert len(session["media"]) == 2
    assert len(session["timeline"]) == 4
    assert session["input_count"] == 1
    assert session["friction_count"] == 1


def test_capture_writes_hash_index_and_passes_eval(tmp_path: Path) -> None:
    result = run_gameplay_capture(FIXTURE, tmp_path)

    assert result.eval_status == "PASS"
    assert result.media_count == 2
    assert result.event_count == 4

    index = json.loads(result.media_index_path.read_text(encoding="utf-8"))
    assert len(index) == 2
    assert all(len(item["sha256"]) == 64 for item in index)
    assert all(item["bytes"] > 0 for item in index)
    assert all((result.root / item["copied_path"]).is_file() for item in index)

    eval_result = json.loads(result.eval_path.read_text(encoding="utf-8"))
    assert all(eval_result["criteria"].values())


def test_capture_rejects_unknown_media_reference(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE, broken)
    timeline = broken / "timeline.jsonl"
    text = timeline.read_text(encoding="utf-8")
    timeline.write_text(
        text.replace('"media_id":"frame-reveal"', '"media_id":"missing-frame"'),
        encoding="utf-8",
    )

    with pytest.raises(GameplayCaptureError, match="unknown media_id"):
        load_capture_session(broken)
