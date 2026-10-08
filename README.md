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

**MGSF-M0.5: QUIC Transport Probe / Network Evidence Harness - incubation**, with **MGSF-M0.6 to M0.8: EdenSpark Agent-Native Prototype Loop - incubation** in parallel.

Current lifecycle:

```text
playtest-report    active
gameplay-capture   active
quic-transport-probe incubation
edenspark-agent-adapter incubation
edenspark-autonomous-playtest incubation
prototype-promotion-gate incubation
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

## EdenSpark prototype loop

The agent-native path keeps engine control inside the EdenSpark project's own MCP configuration and uses Codex as the MCP client:

```text
game hypothesis
  -> mgsf edenspark-plan
  -> codex exec
  -> EdenSpark MCP
  -> inspect / compile / play / input / screenshot / logs
  -> hashed MGSF evidence
  -> retry or promotion gate
```

Fixture CI proves the contract but always remains `HOLD`. A live `PASS` requires a successful recorded `codex-exec` run plus a preserved artifact whose SHA-256 can be verified.

Commands:

```text
mgsf edenspark-plan fixtures/edenspark/mission-neon-001.json
mgsf edenspark-eval <project> <mission.json> <result.json> --runner-record <runner.json>
mgsf edenspark-loop <project> <mission.json> --max-iterations 3
mgsf prototype-promote <evaluation.json> [<evaluation.json> ...]
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

- workflow run `36494396400`
- job `109170434996`
- 15 tests passed
- executable version check passed
- bundled demo produced one finding and PASS
- sample analyze produced one finding and PASS
- packaged files: 14
- product ZIP: 8,142,722 bytes
- ZIP SHA-256: `4dbb4a53f95c56fc7177cbe653542ec28add4e84beaa5e0d9a59bb4676f204a2`
- artifact: `11002044584`

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
- `docs/MGSF_M0_5_QUIC_TRANSPORT_PROBE.md` - transport measurement contract
- `docs/MGSF_M0_6_TO_M0_8_EDENSPARK_PROTOTYPE_LOOP.md` - agent-native prototype and promotion contract
- `src/mgsf/edenspark_agent_adapter.py` - mission compiler, Codex runner, evidence evaluator, retry loop
- `src/mgsf/prototype_promotion.py` - PROMOTE / ITERATE / HOLD gate
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
- Do not treat an agent claim as proof of an engine action without runner and artifact evidence.
- Deterministic EdenSpark fixtures must remain HOLD and may not be described as live engine dogfood.
- Autonomous prototype loops must not publish or submit games.
- Keep downloaded product behavior local unless a future network feature is explicitly disclosed.
- Do not call the preview paid-release-ready until external-user and final legal/third-party review gates pass.

## Next boundary

**MGSF-M0.5: QUIC Transport Probe / Network Evidence Harness**

The milestone establishes packet-shape metrics and provenance-safe deterministic evidence for UDP, QUIC Stream, and QUIC Datagram. Fixture evidence never passes the promotion gate.

Run:

```text
mgsf transport-probe fixtures/network/sega-quic-baseline.json --output-root evidence/quic-probe
```

The previously planned External Tester Preview moves to the next unallocated milestone after M0.5.


Parallel agent-native boundary: run the first real EdenSpark dogfood mission on a local EdenSpark project with its generated MCP configuration. The target proof is one recorded Codex run that inspects the scene, compiles, plays, simulates input, preserves a screenshot or equivalent artifact, checks logs, and earns PASS.
