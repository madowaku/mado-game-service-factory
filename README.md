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

**MGSF-M0.4: Windows Product Pack — complete**

Current lifecycle:

```text
playtest-report    active
gameplay-capture   active
Windows product    preview verified
```

The system now supports both the internal evidence loop and a portable external-facing Windows preview:

```text
run game
  -> capture rendered frames
  -> preserve input/result timeline
  -> hash media evidence
  -> generate playtest finding
  -> package as mado-playtest.exe
  -> ship sample + docs + release manifest in a ZIP
```

## Windows product preview

Product:

`MADO Playtest Evidence 0.4.0`

Customer-facing commands:

```text
mado-playtest.exe self-check
mado-playtest.exe demo
mado-playtest.exe analyze <capture-dir>
mado-playtest.exe godot <godot-project> [--godot <Godot.exe>]
```

Windows verification:

- workflow run `36493989574`
- job `109169128163`
- 15 tests passed
- executable version check passed
- bundled demo produced one finding and PASS
- sample analyze produced one finding and PASS
- packaged files: 14
- product ZIP: 8,141,141 bytes
- ZIP SHA-256: `690921e45c71308e6f4442fb10e411775349b7b5a96d12ba45e0cc259bdd553b`
- artifact: `11001819146`

## Active game-evidence services

### playtest-report

Turns MGEL-compatible friction evidence into traceable developer-facing findings.

### gameplay-capture

Preserves media, timestamps, SHA-256 integrity, and captured friction. A Godot adapter has proven direct `recorded_gameplay_capture` with real 1280x720 PNG frames.

## Product pack

```text
MADO-Playtest-Evidence-0.4.0-win-x64/
├── mado-playtest.exe
├── README.txt
├── PRIVACY.txt
├── PRODUCT_LICENSE.txt
├── THIRD_PARTY_NOTICES.txt
├── SUPPORT.txt
├── RELEASE_NOTES.txt
├── RELEASE-MANIFEST.json
└── examples/
    ├── sample-capture/
    └── sample-report/
```

The product executable has no intentional telemetry or automatic cloud upload in 0.4.0.

## Repository map

- `AGENTS.md` - Codex operating contract and guardrails
- `docs/MADO_GAME_SERVICE_FACTORY_SPEC.md` - Factory specification
- `docs/MGSF_M0_2_REAL_GAME_DOGFOOD_BRIDGE.md` - real-game bridge
- `docs/MGSF_M0_3_GAMEPLAY_EVIDENCE_CAPTURE.md` - capture contract
- `docs/MGSF_M0_3B_GODOT_CAPTURE_ADAPTER.md` - direct Godot adapter
- `docs/MGSF_M0_4_WINDOWS_PRODUCT_PACK.md` - Windows packaging
- `docs/ITCH_IO_PRODUCTIZATION.md` - commercialization gate
- `product/` - customer-facing package documents
- `packaging/windows/` - frozen executable build inputs
- `scripts/build_windows_product.py` - versioned pack builder
- `dogfood/` - real-project and product proof
- `src/mgsf/` - Factory, services, adapters, and product CLI

## Guardrails

- Do not call modeled psychometric values human measurements.
- Do not call reconstructed media screenshots.
- Preserve source and media provenance.
- Keep downloaded product behavior local unless a future network feature is explicitly disclosed.
- Do not call the preview paid-release-ready until external-user and final legal/third-party review gates pass.

## Next boundary

**MGSF-M0.5: External Tester Preview**

The highest-value evidence now comes from someone who did not build the system: can they unzip it, understand it, run the demo, and get useful evidence without guidance?
