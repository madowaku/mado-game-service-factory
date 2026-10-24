---
name: gameplay-mechanics-intelligence
description: Suggest sourced gameplay mechanics and art direction tags before building small Godot or LittleJS prototypes.
---

# Gameplay Mechanics Intelligence
Use the offline catalog first. Run:
```bash
PYTHONPATH=src python -m mgsf.gameplay_intelligence "<experience prompt>" --engine godot
```
Use `--engine littlejs` for browser prototypes. Explain each mechanic with source URL and provenance; treat `manual_reference_unverified` as a review requirement. Do not imply these summaries are directly extracted from the source. Style tags are local ideas, not an official taxonomy. If no match exists, suggest manual research rather than fabricating a citation. Obtain human acceptance criteria and build only in a disposable workspace. Never claim a running engine or successful playtest without artifact hashes and real runner evidence. All recommendations remain HOLD; pass observed results through the existing MGSF quality gate.
