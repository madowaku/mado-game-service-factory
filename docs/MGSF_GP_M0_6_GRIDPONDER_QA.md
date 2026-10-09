# MGSF-GP-M0.6: GridPonder Intake / Deterministic Puzzle QA Harness

## Milestone compatibility

MGSF-M0.6 to M0.8 already names the EdenSpark Agent-Native Prototype Loop.
This is an **additive** track named **MGSF-GP-M0.6**. It does not replace
EdenSpark and does not alter existing CLI commands or the Windows product.

## Architecture and trust boundary

A local, separately checked-out GridPonder repository supplies the real
Python TurnEngine, loader and gold-path parser. MGSF does **not** fork or
reimplement game semantics and performs no network access or installation.

The source API was reviewed at commit
4aa72a0602f81f29750ae688117a3d57e907d9da.

The parent runs an isolated Python worker **twice per level** to verify
both that the authoritative Gold Path wins and that the outcomes are
deterministic across separate processes. Each step records the action,
parameters, accepted flag, events count, win/loss state and a SHA-256 digest
of the canonicalized engine state (board/actors, counters, progress,
one-shot rules and pending move).

The worker imports the upstream engine Python package, not executable code
from the DSL game pack. Only use a trusted, reviewed GridPonder checkout.

## Usage

    mgsf gridponder-qa /path/to/GridPonder/packs/carrot_quest \
      --gridponder-root /path/to/GridPonder \
      --level fw_001 \
      --output-root evidence

Omit --level to replay all entries of type level in game.json levelSequence.
Repeat --level to select several. --timeout-seconds controls the timeout for
each independent worker (default: 120 seconds).

Output: evidence/gridponder/<pack-name>/evaluation.json

## Semantics and evidence

- PASS: every selected level has an accepted winning Gold Path and both
  independent state traces match.
- FAIL: a rejected action, divergent trace, non-winning Gold Path, worker
  error or timeout.
- HOLD: no failure, but at least one selected level is missing a Gold Path.

A passing replay verifies **Python engine semantics only**. It does not prove
Dart/Python parity, visual correctness, human playability, or actual gameplay
capture. All results deliberately retain promotion_gate.status=HOLD.
The service stays at incubation until cross-engine, real-game evidence exists.

The Evidence Bundle contains both execution traces, paths plus SHA-256 hashes
of the selected pack JSON and selected engine entrypoint files, an upstream
Git SHA if available, the summary, and explicit provenance flags.

## Acceptance

- Unit tests cover PASS, FAIL, divergence, missing Gold Path, missing level,
  rejected action, replay error and canonical ordering.
- CI checks out the upstream commit pinned above and replays Carrot Quest
  fw_001 through the **real** Python engine (no mocked fixture).
- The existing tests, CLI commands and EdenSpark contracts remain intact.
- The pinned source is a known API contract, not an automatic upstream upgrade.
  Updates must explicitly review the upstream commit and rerun the QA suite.
