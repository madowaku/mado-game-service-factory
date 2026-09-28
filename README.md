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

**MGSF-M0.2: Real Game Dogfood Bridge — complete**

最初のサービス **Game Playtest AI / `playtest-report`** は `active` に昇格しました。

```text
candidate
  -> incubation
  -> deterministic fixture PASS
  -> real-project dogfood PASS
  -> active
```

## Quick start

Requirements: Python 3.11+

```bash
python -m pip install -e ".[dev]"
mgsf validate-catalog
mgsf list
pytest
```

Deterministic fixture:

```bash
mgsf playtest-report fixtures/playtest-report/mgel-session-001
```

Real-project dogfood:

```bash
mgsf dogfood-playtest-report \
  dogfood/vertical-slice-c6-near-miss/record.json \
  dogfood/vertical-slice-c6-near-miss/runtime_log.txt
```

## MGSF-M0.2

The Real Game Dogfood Bridge converts provenance-backed real-project headless evidence into an MGEL-compatible bundle and immediately feeds it into `playtest-report`.

First target: `madowaku/vertical-slice`.

Verified source evidence:

- Godot 4.7.2 stable
- GitHub Actions run `33968989364`
- job `101314031594`
- `Tests: 794 passed`
- `Failures: 0`
- `C6 playfeel: 24 / 0 failures`

Factory dogfood run `36438711683` produced:

```text
service=playtest-report findings=1 eval=PASS
dogfood=playtest-report findings=1 eval=PASS
8 passed in 0.05s
```

The C6 one-cell-early swing becomes one traceable medium-severity `near_miss` finding.

### Evidence honesty

The bridge distinguishes runtime facts from modeled player-state values.

```text
evidence_class = real_project_headless_test
psychometric_values = deterministic_model_not_human_measurement
```

So MGSF does not pretend that modeled confusion or surprise came from a human playtester.

## Evidence outputs

```text
evidence/
├── real-game-bridge/
│   └── <source>/<session>/
│       ├── manifest.json
│       ├── source_record.json
│       ├── runtime_log.txt
│       ├── bridge_eval.json
│       ├── dogfood_eval.json
│       └── mgel/
└── playtest-report/
    └── <source>/<session>/
        ├── manifest.json
        ├── report.json
        ├── report.md
        ├── eval.json
        └── run.log
```

CI publishes the generated `ci-evidence` tree as a GitHub Actions artifact.

## Repository map

- `AGENTS.md` - Codex operating contract and guardrails
- `docs/MADO_GAME_SERVICE_FACTORY_SPEC.md` - Factory specification
- `docs/MGSF_M0_2_REAL_GAME_DOGFOOD_BRIDGE.md` - real-game bridge contract
- `catalog/services.yaml` - machine-readable service catalog
- `services/active/playtest-report/` - active service contract
- `dogfood/` - real-project dogfood records
- `evals/` - promotion and service evals
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
- Prove value in the order CLI -> local API -> Web UI -> hosted service.

## Next boundary

**MGSF-M0.3: higher-fidelity gameplay evidence.**

The next useful move is a live or recorded gameplay capture adapter, screenshot/video evidence, or human-observation ingestion, not more product chrome.
