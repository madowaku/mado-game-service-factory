# MGSF-M1.2: Adaptive GameDev Skill Router (incubation)

Upstream: https://github.com/gamedev-skills/awesome-gamedev-agent-skills

## Boundary
This is an **offline, planning-only adapter**, not a copy or execution of upstream skills.
It does not download arbitrary content, install dependencies, invoke agents, run an
engine, or change any existing Godot/Unity workflows. The upstream catalog is an
untrusted, moving dependency. Audit and pin a commit before loading its SKILL.md
files, and review each selected skill for executable commands, exfiltration and
license restrictions. The names/paths here are a curated subset, not a complete
mirror of the upstream catalog.

## How to run
```bash
PYTHONPATH=src python -m mgsf.gamedev_skill_router /path/to/godot/project "ローグライクのダンジョン"
PYTHONPATH=src python -m mgsf.gamedev_skill_router /path/to/unity/project "RPGのインベントリ" --output evidence/skill-routing/selection.json
pytest -q tests/test_gamedev_skill_router.py
```

Detect the engine from `project.godot` or Unity `Assets` and
`ProjectSettings/ProjectVersion.txt`. Reject conflicting project
fingerprints. Explicit `--engine` is available when metadata is absent.

## Quality contract
- Every plan returns **HOLD**, `provenance=planning_only`, and
  `execution_performed=false`. A routing fixture is not gameplay evidence.
- Never promote a game from agent assertion or the skill selection itself.
- Preserve current live-run, screenshots, artifact SHA-256 and runner evidence gates.
- Full A/B game-build comparison and live Windows Godot/Unity dogfood are **pending**.
- Compare skill-on/off with identical prompt, engine, budget and seed when
  available; preserve raw capture, failures, costs and human-review notes.
- This module contains no background installer, network activity or telemetry.

## Future work
Pin and audit upstream skill bodies, integrate into existing CLI without
regression, establish real-engine A/B runs, connect evidence to cockpit UI, and
only then consider status promotion. Keep external publishing disabled.
