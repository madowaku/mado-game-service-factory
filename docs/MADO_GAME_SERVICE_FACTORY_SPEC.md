# MADO Game Service Factory Specification v0.1

## 1. Purpose
MADO Game Service Factory (MGSF) turns recurring game-development friction into small reusable services.

Its primary output is not code volume. Its primary output is validated utility backed by evidence.

## 2. Core loop

DISCOVER -> SELECT -> SPEC -> BUILD -> DOGFOOD -> EVAL -> SHIP -> OBSERVE -> IMPROVE/RETIRE

## 3. Candidate selection
A candidate should normally satisfy:
- problem_frequency: medium or high
- automation_fit: high
- evidence_available: true
- dogfoodable: true
- reusable: true
- implementation_scope: small

## 4. Service contract
Every service defines:
- problem
- user
- input
- output
- happy_path
- failure_modes
- evidence
- eval
- mvp_boundary

## 5. Lifecycle
### candidate
Interesting problem, not yet selected.

### incubation
Selected and being proven.

### active
Runnable, dogfooded, evidence-backed, and eval-passing.

### retired
No longer worth maintaining, superseded, or repeatedly failing eval.

## 6. Evidence Bundle
Minimum bundle:
- manifest.json
- run metadata
- input snapshot or stable reference
- output artifact
- eval result
- logs
- notes on limitations

Real-project evidence should be preferred over synthetic evidence. Fixtures exist for determinism, not as the sole proof of value.

## 7. Factory architecture
```
factory/
  discover/
  select/
  eval/
  ship/

services/
  incubation/
  active/
  retired/

catalog/
  services.yaml

missions/
  mission-001.md

fixtures/
evidence/
```

## 8. Guardrails
MGSF must avoid premature SaaS architecture. CLI-first is the default progression:

CLI -> local API -> web UI -> hosted service

A later layer is justified only after the previous layer demonstrates value.

## 9. MGSF-M0 completion criteria
- AGENTS.md establishes the operating contract.
- Service catalog exists and is machine-readable.
- Mission 001 exists.
- A CLI can inspect and validate the catalog.
- Tests cover catalog loading and basic validation.
- Repository layout supports later incubation services.

## 10. Next milestone
MGSF-M0.1 Candidate Discovery:
inventory existing MADO game-development repositories and produce ten service candidates with evidence links and selection rationale.
