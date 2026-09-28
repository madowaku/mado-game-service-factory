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

**MGSF-M0.3: Gameplay Evidence Capture**

Current lifecycle:

```text
playtest-report    active
gameplay-capture   incubation
```

M0.3 adds a media-aware evidence layer so screenshots, video, and input/result timing can survive into later QA and playtest analysis.

## Quick start

Requirements: Python 3.11+

```bash
python -m pip install -e ".[dev]"
mgsf validate-catalog
mgsf list
pytest
```

Deterministic playtest report:

```bash
mgsf playtest-report fixtures/playtest-report/mgel-session-001
```

Real-project headless dogfood:

```bash
mgsf dogfood-playtest-report \
  dogfood/vertical-slice-c6-near-miss/record.json \
  dogfood/vertical-slice-c6-near-miss/runtime_log.txt
```

Gameplay capture contract fixture:

```bash
mgsf gameplay-capture \
  fixtures/gameplay-capture/vertical-slice-reconstruction
```

## Gameplay Evidence Capture

Input:

```text
capture.json
timeline.jsonl
media files
```

Output:

```text
evidence/gameplay-capture/<capture_id>/<session_id>/
├── manifest.json
├── media_index.json
├── timeline.jsonl
├── eval.json
└── media/
```

Each media item receives its SHA-256, byte size, timestamp, and stable media ID. Timeline events are monotonic and may link directly to captured media.

### Evidence classes

```text
recorded_gameplay_capture
reconstructed_from_verified_state
synthetic_capture_fixture
```

They are intentionally different.

The current committed M0.3 fixture uses `reconstructed_from_verified_state`. Its C6 SVG frames are explanatory reconstructions based on separately verified `vertical-slice` state. They are **not screenshots**.

`gameplay-capture` remains in incubation until a direct `recorded_gameplay_capture` from a real running game passes the same eval.

## Existing M0.2 evidence

The first active `playtest-report` service is backed by `madowaku/vertical-slice`:

- Godot 4.7.2 stable
- source GitHub Actions run `33968989364`
- `Tests: 794 passed`
- `Failures: 0`
- `C6 playfeel: 24 / 0 failures`

## Repository map

- `AGENTS.md` - Codex operating contract and guardrails
- `docs/MADO_GAME_SERVICE_FACTORY_SPEC.md` - Factory specification
- `docs/MGSF_M0_2_REAL_GAME_DOGFOOD_BRIDGE.md` - real-game bridge contract
- `docs/MGSF_M0_3_GAMEPLAY_EVIDENCE_CAPTURE.md` - capture contract
- `catalog/services.yaml` - machine-readable service catalog
- `services/active/` - promoted services
- `services/incubation/` - services still proving their evidence
- `dogfood/` - real-project dogfood records
- `evals/` - service and promotion evals
- `fixtures/` - deterministic fixtures
- `src/mgsf/` - Factory and service CLI
- `tests/` - deterministic checks

## Guardrails

- Do not start with SaaS UI.
- Do not start with auth or billing.
- Do not build speculative infrastructure.
- Do not treat fixture success as active-service proof.
- Do not promote without real-project evidence.
- Do not call modeled psychometric values human measurements.
- Do not call reconstructed media screenshots.
- Prove value in the order CLI -> local API -> Web UI -> hosted service.

## M0.3 next gate

Add an engine or desktop recorder that generates a real `recorded_gameplay_capture` bundle without changing the capture contract.
