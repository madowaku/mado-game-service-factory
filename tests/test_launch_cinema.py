import json
from pathlib import Path

import pytest

from mgsf.launch_cinema import create_mission_pack, load_brief


BASE = {
    "schema": "mgsf.launch-cinema-brief.v1", "id": "window-teaser-001",
    "project_repository": "madowaku/madowaku.github.io", "product_url": None,
    "goal": "Show a window into other worlds", "audience": "curious players",
    "creative_direction": "Hand-drawn atmospheric windows", "cta": "Open a window",
    "mode": "opening_only", "aspect_ratio": "16:9", "duration_seconds": 15,
    "reference_url": None, "reference_policy": "review_before_reuse",
    "ava_credit_limit": 0, "publication_approved": False,
    "must_keep": ["Use real madowaku assets", "No invented gameplay"],
}


def write(tmp_path: Path, obj: dict) -> Path:
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_plan_is_deterministic_and_holds_without_running(tmp_path):
    path = write(tmp_path, BASE)
    root = create_mission_pack(path, tmp_path / "out")
    data = json.loads((root / "mission.json").read_text(encoding="utf-8"))
    first = (root / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    create_mission_pack(path, tmp_path / "out")
    assert data["gate"] == "HOLD"
    assert data["render_verified"] is False
    assert data["release_approved"] is False
    assert data["upstream"]["revision"] == "272410c0a42318b3a0cd85e025e8ed5856637b04"
    assert len(data["brief_sha256"]) == 64
    assert first == (root / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "zero spend" in first
    assert "UNCONFIRMED" in first


def test_repository_launch_brief_is_valid():
    brief = load_brief(Path("fixtures/launch-cinema/madowaku-window-teaser-001.json"))
    assert brief["publication_approved"] is False
    assert brief["ava_credit_limit"] == 0


@pytest.mark.parametrize("key,value", [
    ("id", "../bad"), ("id", "UPPER"), ("duration_seconds", 60),
    ("aspect_ratio", "21:9"), ("publication_approved", True),
    ("reference_policy", "copy_anything"), ("product_url", "file:///secret"),
    ("product_url", "https://user:pass@example.org"), ("ava_credit_limit", -1),
    ("ava_credit_limit", True), ("must_keep", []),
])
def test_rejects_unsafe_or_invalid_brief(tmp_path, key, value):
    bad = {**BASE, key: value}
    with pytest.raises(ValueError):
        load_brief(write(tmp_path, bad))
