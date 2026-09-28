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

**MGSF-M0: Factory Skeleton**

Factoryの仕事は「たくさん作る」ことではありません。実際のゲーム開発でdogfoodでき、Evidence Bundleを残し、evalを通過したサービスだけを育てます。

## Quick start

Requirements: Python 3.11+

```bash
python -m pip install -e ".[dev]"
mgsf validate-catalog
mgsf list
pytest
```

## Mission 001

最初の自走ミッションは、既存MADO資産からゲーム開発サービス候補を10件抽出し、3件をMVP候補に絞り、最小の1件を実装・dogfood・evalすることです。

現在のfirst buildは **Game Playtest AI / playtest-report**。

候補と根拠は `missions/mission-001-candidates.yaml` に保存しています。

## Repository map

- `AGENTS.md` - Codexの自走契約とguardrail
- `docs/MADO_GAME_SERVICE_FACTORY_SPEC.md` - Factory仕様 v0.1
- `catalog/services.yaml` - サービスのmachine-readable catalog
- `missions/mission-001.md` - 最初の自走ミッション
- `missions/mission-001-candidates.yaml` - 10候補とMVP選定
- `src/mgsf/` - Factory CLI
- `tests/` - deterministic checks
- `evidence/` - 生成Evidence Bundle。git管理外

## Guardrails

- SaaS UIから作らない
- auth / billingから作らない
- speculative infrastructureを作らない
- fixtureだけで成功扱いしない
- Evidence Bundleなしでactiveへ昇格しない
- CLI -> local API -> Web UI -> hosted service の順で価値を証明する

## Related MADO foundations

Mission 001は既存の `mado-game-experience-loop`, `mado-loop`, `vertical-slice`, `mado-system-one`, `mado-vibe-shipping` を最初の観測対象にしています。

次の実装境界は **MGSF-M0.1: playtest-report incubation service** です。
