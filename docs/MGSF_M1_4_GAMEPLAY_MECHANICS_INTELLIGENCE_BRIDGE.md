# MGSF-M1.4 Gameplay Mechanics Intelligence Bridge

Status: **incubation / HOLD**. This is a small, offline, opt-in reference engine, not an autonomous prototype generator.

## Goal
Translate a gameplay experience prompt into sourced mechanic candidates, optional art-style tags and engine-specific prototype hints. Reuse the existing MGSF capture/playtest/prototype promotion flow rather than inventing a new runtime.

## Source and rights
- Human-curated original seed summaries with explicit source URLs, no bulk crawl or scraped images.
- Gameplay Atlas: https://gameplayatlas.loopyhop.com/
- Game Art Style: https://gameartstyle.loopyhop.com/
- Source URL **does not imply** permission to redistribute source text, screenshots or data.
- `manual_reference_unverified` means a pointer for manual source checking, not a verified reproduction of site content.
- `style_tags` are local descriptive tags, **not** claimed official Game Art Style taxonomy.
- Do not ship/republish material until licensing and source details are independently reviewed.

## Run locally
```bash
PYTHONPATH=src python -m mgsf.gameplay_intelligence "stealth disguise" --engine godot
PYTHONPATH=src python -m mgsf.gameplay_intelligence "自動化" --engine littlejs
PYTHONPATH=src pytest -q tests/test_gameplay_intelligence.py
```

The script is entirely stdlib; it makes no HTTP calls, starts no game engine, and does not modify a Godot project. Results contain original summaries, provenance, candidate style tags and implementation hints, but **always** return `gate: HOLD`. Empty-match queries remain empty instead of inventing candidates.

## Integration boundary
1. Search curated mechanics offline and choose a candidate.
2. Review upstream citations/rights and define human acceptance criteria.
3. Build a disposable Godot or LittleJS prototype in an isolated project.
4. Run existing MGSF gameplay-capture and playtest-report on a recorded engine run.
5. Only pass the existing prototype-promotion gate with runner evidence, artifact hashes, license review and human playability judgment.

## Deferred
Automatic harvesting, multilingual semantic/vector search, cockpit UI integration, live game builds, direct website/API integration and verified mapping to a Game Art Style taxonomy. Validate manual usefulness before expanding.

## Acceptance
- Seed and schema validation, deterministic sorting, Japanese keyword and dual-engine hints, empty-query/no-match behavior.
- No modification to existing Godot adapter or service interfaces.
- Fixture-only evidence **never** earns PASS.
