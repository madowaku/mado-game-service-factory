# MADO Game Service Factory

ゲーム開発の反復作業・専門知識の壁・品質確認の面倒を、小さく再利用可能なサービスへ変換する evidence-driven factory。

```
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

**MGSF-M0.1: playtest-report incubation service**

Factoryの仕事は「たくさん作る」ことではありません。実際のゲーム開発でdogfoodでき、Evidence Bundleを残し、evalを通過したサービスだけを育てます。

## Quick start

Requirements: Python 3.11+

```bash
python -m pip install -e ".[dev]"
mgsf validate-catalog
mgsf list
pytest
```

Run the deterministic playtest-report fixture:

```bash
mgsf playtest-report fixtures/playtest-report/mgel-session-001
```

Output:

```text
evidence/playtest-report/fixture-001/session-001/
├── manifest.json
├── report.json
├── report.md
├── eval.json
└── run.log
```

## MGSF-M0.1

`playtest-report` consumes an MGEL M0 Evidence Bundle and converts each friction event into one developer-facing finding with:

- deterministic severity
- source event ID and step index
- player impact
- reproduction steps
- expected vs actual result
- recommendation
- confusion / surprise evidence

The service fails closed if source identity, event counts, friction counts, or event traceability do not agree.

The committed fixture is expected to produce one high-severity finding for `event-001` and a passing service eval.

**Important:** passing the deterministic fixture moves the service into incubation only. Promotion to `active` still requires real-project dogfood evidence.

## Mission 001

The first autonomous mission discovered ten service candidates and selected three MVPs. The first build is **Game Playtest AI / playtest-report**.

Candidate rationale lives in `missions/mission-001-candidates.yaml`.

## Repository map

- `AGENTS.md` - Codex operating contract and guardrails
- `docs/MADO_GAME_SERVICE_FACTORY_SPEC.md` - Factory specification v0.1
- `catalog/services.yaml` - machine-readable service catalog
- `missions/` - autonomous factory missions
- `services/incubation/playtest-report/` - M0.1 service contract
- `evals/playtest-report.yaml` - M0.1 promotion eval
- `fixtures/playtest-report/` - deterministic MGEL input fixture
- `src/mgsf/` - Factory and service CLI
- `tests/` - deterministic checks
- `evidence/` - generated Evidence Bundles, excluded from git

## Guardrails

- Do not start with SaaS UI.
- Do not start with auth or billing.
- Do not build speculative infrastructure.
- Do not treat fixture success as active-service proof.
- Do not promote without an Evidence Bundle.
- Prove value in the order CLI -> local API -> Web UI -> hosted service.

## Related MADO foundations

Mission 001 currently builds on `mado-game-experience-loop`, `mado-loop`, `vertical-slice`, `mado-system-one`, and `mado-vibe-shipping`.

Next gate: **dogfood playtest-report against non-fixture game evidence before active promotion**.
