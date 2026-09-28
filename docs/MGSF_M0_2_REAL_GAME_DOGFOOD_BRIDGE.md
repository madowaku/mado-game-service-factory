# MGSF-M0.2 Real Game Dogfood Bridge

## Goal

Bridge evidence from a real game repository into the MGEL M0 contract, then run the existing `playtest-report` service against that evidence.

M0.2 intentionally distinguishes three things:

1. **Runtime-observed facts** from a real game project and engine test.
2. **Scenario facts** anchored to the tested project source.
3. **Experience-model values** such as confusion and surprise, which are deterministic bridge policy values, not human measurements.

## First dogfood target

Repository: `madowaku/vertical-slice`

Recorded provenance:

- source head: `7597c87bae0e66afbdb09165496843da10b0a221`
- tested PR merge: `6a2e49bd3bc20b18ccd99a825fa332380685fc4c`
- merged main commit: `9e06cdefdcad9b951fb64bae6b50873702aec03f`
- GitHub Actions run: `33968989364`
- job: `101314031594`
- engine: Godot 4.7.2 stable
- result: `Tests: 794 passed`, `Failures: 0`
- C6 suite: `C6 playfeel: 24 / 0 failures`

The C6 test contains a deterministic one-cell-early swing scenario whose reveal verifies that the watermelon was next door.

## Bridge input

A recorded real-game contract has:

- repository and commit provenance
- workflow run and job provenance
- engine identity
- required runtime log markers
- scenario observation/action/result
- explicit evidence class
- explicit bridge policy for modeled experience values

Accepted evidence class in M0.2:

`real_project_headless_test`

## Output

```text
evidence/
├── real-game-bridge/
│   └── <fixture_id>/<session_id>/
│       ├── manifest.json
│       ├── source_record.json
│       ├── runtime_log.txt
│       ├── bridge_eval.json
│       ├── dogfood_eval.json
│       └── mgel/
│           ├── session.json
│           ├── experience_trace.jsonl
│           ├── friction_events.json
│           └── summary.json
└── playtest-report/
    └── <fixture_id>/<session_id>/
        ├── manifest.json
        ├── report.json
        ├── report.md
        ├── eval.json
        └── run.log
```

## Honesty boundary

The bridge must not claim that a human player reported confusion or surprise.

M0.2 records:

`psychometric_values = deterministic_model_not_human_measurement`

The real evidence proves that the project, scenario contract, and tested outcome exist in a real Godot project. It does not convert modeled player state into human-subject evidence.

## Pass criteria

The bridge passes when:

- every required runtime marker is present;
- repository and workflow provenance are present;
- evidence class is explicitly real-project headless test evidence;
- an MGEL-compatible bundle is written;
- modeled psychometric values are disclosed.

Dogfood passes when:

- bridge eval passes;
- playtest-report eval passes;
- source identity survives the bridge;
- the real-game friction event produces a traceable report finding.
