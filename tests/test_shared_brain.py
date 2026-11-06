"""M0.1 offline-only checks. Tests never touch Notion or OAuth."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.shared_brain_check import validate


ROOT = Path(__file__).resolve().parents[1]


def test_valid_seed_and_mcp_configs():
    assert validate(ROOT) == []


@pytest.mark.parametrize("field,value", [
    ("status", "not-a-status"),
    ("confidence", "verified"),
    ("created_at", "2026-99-99"),
    ("publish_approved", "yes"),
])
def test_reject_bad_records(tmp_path, field, value):
    (tmp_path / ".codex").mkdir()
    (tmp_path / "shared-brain").mkdir()
    (tmp_path / ".codex/config.toml").write_text((ROOT / ".codex/config.toml").read_text("utf-8"), encoding="utf-8")
    (tmp_path / ".mcp.json").write_text((ROOT / ".mcp.json").read_text("utf-8"), encoding="utf-8")
    data = json.loads((ROOT / "shared-brain/seed.json").read_text("utf-8"))
    data["records"][0][field] = value
    (tmp_path / "shared-brain/seed.json").write_text(json.dumps(data), encoding="utf-8")
    assert validate(tmp_path)


def test_reject_secret_in_seed(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / "shared-brain").mkdir()
    (tmp_path / ".codex/config.toml").write_text((ROOT / ".codex/config.toml").read_text("utf-8"), encoding="utf-8")
    (tmp_path / ".mcp.json").write_text((ROOT / ".mcp.json").read_text("utf-8"), encoding="utf-8")
    data = json.loads((ROOT / "shared-brain/seed.json").read_text("utf-8"))
    data["records"][0]["summary"] = "password=supersecret_password_value"
    (tmp_path / "shared-brain/seed.json").write_text(json.dumps(data), encoding="utf-8")
    assert any("secret" in message for message in validate(tmp_path))
