# Mission 001: First Autonomous Service

## Objective
Use existing MADO game-development work as source material and produce the first evidence-backed reusable service.

## Steps
1. Inventory relevant MADO repositories and artifacts.
2. Extract ten recurring game-development problems.
3. Record ten service candidates.
4. Select three MVP candidates using the factory selection criteria.
5. Choose the smallest candidate with meaningful dogfood potential.
6. Write its service contract.
7. Implement it as a CLI or local tool.
8. Run a deterministic fixture.
9. Run it against at least one real project when accessible.
10. Produce an Evidence Bundle.
11. Run the service eval.
12. Promote to active only if the eval passes.

## Deliverables
- `missions/mission-001-candidates.yaml`
- service spec
- implementation
- fixture
- eval definition
- evidence bundle
- catalog update

## Stop conditions
Stop expansion and return to selection if:
- the MVP requires auth, billing, hosted infrastructure, or a large UI;
- useful evidence cannot be produced;
- the candidate duplicates an existing MADO capability without a clear service boundary;
- the service cannot be dogfooded.

## Success condition
One small service reaches `active` with reproducible evidence. Nine unbuilt candidates are acceptable. One proven tool beats ten speculative products.
