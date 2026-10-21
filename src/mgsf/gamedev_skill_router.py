"""Offline, non-executing skill selection adapter for MGSF-M1.2.

Never installs or executes untrusted upstream skills. The generated plan is
advisory and cannot be used as gameplay evidence or a promotion PASS.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

UPSTREAM = "https://github.com/gamedev-skills/awesome-gamedev-agent-skills"
ENGINE_SKILLS = {
    "godot": {"base": "godot-gdscript", "map": "godot-tilemap", "ui": "godot-ui-control"},
    "unity": {"base": "unity-csharp-scripting", "map": "unity-tilemap-2d", "ui": "game-ui-ux"},
}
TASK_RULES = (
    (r"roguelike|ローグライク|ダンジョン", ("procedural-gen", "roguelike", "map")),
    (r"rpg|ロールプレイ|クエスト|inventory|インベントリ", ("rpg", "save-systems", "ui")),
    (r"platformer|ジャンプ|プラットフォーマー", ("platformer", "game-feel")),
    (r"sprite|スプライト|素材|asset|画風|pixel.art", ("create-game-assets",)),
    (r"ui|hud|メニュー|画面", ("game-ui-ux", "ui")),
    (r"save|load|セーブ|ロード", ("save-systems",)),
    (r"enemy|npc|敵|経路探索|pathfind", ("game-ai",)),
    (r"performance|fps|最適化|遅い", ("performance-optimization",)),
    (r"test|テスト|qa|検証", ("test",)),
)
SKILL_PATHS = {
    "godot-gdscript": "skills/godot/godot-gdscript/SKILL.md",
    "godot-tilemap": "skills/godot/godot-tilemap/SKILL.md",
    "godot-ui-control": "skills/godot/godot-ui-control/SKILL.md",
    "unity-csharp-scripting": "skills/unity/unity-csharp-scripting/SKILL.md",
    "unity-tilemap-2d": "skills/unity/unity-tilemap-2d/SKILL.md",
    "create-game-assets": "skills/disciplines/create-game-assets/SKILL.md",
    "game-ui-ux": "skills/disciplines/game-ui-ux/SKILL.md",
    "save-systems": "skills/disciplines/save-systems/SKILL.md",
    "game-ai": "skills/disciplines/game-ai/SKILL.md",
    "performance-optimization": "skills/disciplines/performance-optimization/SKILL.md",
    "procedural-gen": "skills/disciplines/procedural-gen/SKILL.md",
    "game-feel": "skills/disciplines/game-feel/SKILL.md",
    "roguelike": "skills/genres/roguelike/SKILL.md",
    "rpg": "skills/genres/rpg/SKILL.md",
    "platformer": "skills/genres/platformer/SKILL.md",
}

def detect_engine(project: Path) -> str | None:
    """Inspect only metadata inside the requested project, never sibling projects."""
    if not project.is_dir():
        raise ValueError("project must be an existing directory")
    matches = []
    if (project / "project.godot").is_file():
        matches.append("godot")
    if (project / "Assets").is_dir() and (project / "ProjectSettings" / "ProjectVersion.txt").is_file():
        matches.append("unity")
    if len(matches) > 1:
        raise ValueError("ambiguous engine fingerprint; select a single project root")
    return matches[0] if matches else None

def select_skills(project: Path, request: str, engine: str | None = None) -> dict:
    if not request.strip():
        raise ValueError("request cannot be empty")
    detected = detect_engine(project)
    if engine is not None and engine not in ENGINE_SKILLS:
        raise ValueError("engine must be godot or unity")
    if detected and engine and detected != engine:
        raise ValueError("explicit engine disagrees with project fingerprint")
    selected = detected or engine
    if selected is None:
        return {"schema_version": 1, "decision": "HOLD", "reason": "engine_unknown",
                "engine": None, "skills": [], "provenance": "planning_only",
                "upstream": UPSTREAM, "execution_performed": False}
    names = [ENGINE_SKILLS[selected]["base"]]
    notes = []
    for pattern, additions in TASK_RULES:
        if re.search(pattern, request, flags=re.IGNORECASE):
            for skill in additions:
                if skill == "test":
                    notes.append("Keep existing MGSF engine/headless and visual evidence gates; no fixture-only PASS")
                else:
                    names.append(ENGINE_SKILLS[selected][skill] if skill in ("map", "ui") else skill)
    names = list(dict.fromkeys(names))
    return {"schema_version": 1, "decision": "HOLD", "reason": "advisory_skill_selection",
            "engine": selected, "skills": [{"name": n, "upstream_path": SKILL_PATHS[n]} for n in names],
            "notes": notes, "provenance": "planning_only", "upstream": UPSTREAM,
            "execution_performed": False, "requires_live_evidence": True}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MGSF-M1.2 advisory GameDev Skill Router")
    parser.add_argument("project", type=Path)
    parser.add_argument("request")
    parser.add_argument("--engine", choices=("godot", "unity"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = select_skills(args.project, args.request, args.engine)
    except ValueError as exc:
        parser.error(str(exc))
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
