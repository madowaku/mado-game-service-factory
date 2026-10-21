from pathlib import Path
import pytest

from mgsf.gamedev_skill_router import detect_engine, select_skills

def names(plan):
    return [s["name"] for s in plan["skills"]]

def test_godot_roguelike_selection(tmp_path: Path):
    (tmp_path / "project.godot").write_text("config_version=5", encoding="utf-8")
    plan = select_skills(tmp_path, "ローグライク ダンジョンを作成")
    assert plan["engine"] == "godot"
    assert names(plan) == ["godot-gdscript", "procedural-gen", "roguelike", "godot-tilemap"]
    assert plan["decision"] == "HOLD"
    assert plan["execution_performed"] is False

def test_unity_rpg_selection(tmp_path: Path):
    (tmp_path / "Assets").mkdir()
    (tmp_path / "ProjectSettings").mkdir()
    (tmp_path / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3.0f1")
    plan = select_skills(tmp_path, "RPGのインベントリとセーブを作る")
    assert names(plan) == ["unity-csharp-scripting", "rpg", "save-systems", "game-ui-ux"]
    assert plan["requires_live_evidence"]

def test_unknown_engine_holds(tmp_path: Path):
    assert select_skills(tmp_path, "create a game")["reason"] == "engine_unknown"

def test_conflicting_engine_rejected(tmp_path: Path):
    (tmp_path / "project.godot").touch()
    with pytest.raises(ValueError, match="disagrees"):
        select_skills(tmp_path, "UI", engine="unity")

def test_ambiguous_monorepo_rejected(tmp_path: Path):
    (tmp_path / "project.godot").touch()
    (tmp_path / "Assets").mkdir()
    (tmp_path / "ProjectSettings").mkdir()
    (tmp_path / "ProjectSettings" / "ProjectVersion.txt").touch()
    with pytest.raises(ValueError, match="ambiguous"):
        detect_engine(tmp_path)

def test_duplicate_skills_and_testing_gate(tmp_path: Path):
    (tmp_path / "project.godot").touch()
    plan = select_skills(tmp_path, "HUD UI メニューとテスト")
    assert len(names(plan)) == len(set(names(plan)))
    assert any("fixture-only PASS" in note for note in plan["notes"])

def test_blank_request_is_invalid(tmp_path: Path):
    with pytest.raises(ValueError, match="empty"):
        select_skills(tmp_path, "   ")
