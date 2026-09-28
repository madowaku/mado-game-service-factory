# MADO Game Service Factory

ゲーム開発の反復作業・専門知識の壁・品質確認の面倒を、小さく再利用可能なサービスへ変換する evidence-driven factory。

```text
DISCOVER
  -> SELECT
  -> SPEC
  -> BUILD
  -> DOGFOOD
  -> EVAL
  -> SHIP
  -> OBSERVE
  -> IMPROVE / RETIRE
```

## Current milestone

**MGSF-M0.3b: Godot Capture Adapter — complete**

Current lifecycle:

```text
playtest-report    active
gameplay-capture   active
```

The system now supports a real customer-visible loop:

```text
run Godot game
  -> capture rendered frames
  -> preserve input/result timeline
  -> hash media evidence
  -> bridge friction into MGEL
  -> generate playtest finding
  -> retain exact media evidence
```

## Quick start

Requirements: Python 3.11+

```bash
python -m pip install -e ".[dev]"
mgsf validate-catalog
mgsf list
pytest
```

Capture an existing contract:

```bash
mgsf gameplay-capture <capture-dir>
```

Capture through a playtest report:

```bash
mgsf capture-playtest-report <capture-dir>
```

Run a Godot capture scene:

```bash
mgsf godot-capture <godot-project> \
  --godot /path/to/godot
```

On Linux CI, add `--xvfb`.

## MGSF-M0.3b proof

First direct target:

`madowaku/vertical-slice`

Capture SHA:

`f0514229d7f2036ec25646d09e3647c8d870dadb`

Factory CI:

- run `36488219481`
- job `109150207262`
- adapter eval: PASS
- finding count: 1
- tests: 12 passed
- evidence artifact: `11000425066`

Direct frames:

```text
before-swing.png
1280 x 720 RGBA
sha256 ac5c0ec22875fe6222021fc82d420abd3195a518904cbd39febd8ff953d7ddcd

reveal.png
1280 x 720 RGBA
sha256 126240e5e70057d17be6322137d3c662c4361a993ce39b2cf4157a2322a98d51
```

The adapter eval explicitly verified:

```text
recorded_gameplay_capture = true
direct_media_reaches_finding = true
status = PASS
```

## Fresh checkout behavior

The Godot adapter performs a headless editor preflight before capture so fresh clones can generate/import Godot's project metadata and global script-class cache.

Then it launches the capture scene with an actual display surface. Linux CI uses Xvfb; local Windows usage does not need it.

## Evidence classes

```text
recorded_gameplay_capture
reconstructed_from_verified_state
synthetic_capture_fixture
```

They remain intentionally separate.

Only `recorded_gameplay_capture` is treated as direct gameplay media.

## Repository map

- `AGENTS.md` - Codex operating contract and guardrails
- `docs/MADO_GAME_SERVICE_FACTORY_SPEC.md` - Factory specification
- `docs/MGSF_M0_2_REAL_GAME_DOGFOOD_BRIDGE.md` - real-game bridge contract
- `docs/MGSF_M0_3_GAMEPLAY_EVIDENCE_CAPTURE.md` - capture contract
- `docs/MGSF_M0_3B_GODOT_CAPTURE_ADAPTER.md` - direct Godot adapter
- `docs/ITCH_IO_PRODUCTIZATION.md` - productization gate
- `catalog/services.yaml` - machine-readable service catalog
- `services/active/` - promoted services
- `dogfood/` - real-project dogfood records
- `evals/` - service and promotion evals
- `fixtures/` - deterministic fixtures
- `src/mgsf/` - Factory and service CLI
- `tests/` - deterministic checks

## Guardrails

- Do not start with SaaS UI.
- Do not start with auth or billing.
- Do not build speculative infrastructure.
- Do not call modeled psychometric values human measurements.
- Do not call reconstructed media screenshots.
- Preserve source and media provenance.
- Prove value before adding product chrome.

## Next boundary

The highest-value next step is a portable Windows product package for external testers, not another internal service layer.
