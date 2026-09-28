# Vertical Slice C6 dogfood result

Status: **PASS**

## Source evidence

- Repository: `madowaku/vertical-slice`
- Source head: `7597c87bae0e66afbdb09165496843da10b0a221`
- Tested PR merge: `6a2e49bd3bc20b18ccd99a825fa332380685fc4c`
- Main merge: `9e06cdefdcad9b951fb64bae6b50873702aec03f`
- GitHub Actions run: `33968989364`
- Job: `101314031594`
- Engine: Godot 4.7.2 stable
- Runtime summary: `Tests: 794 passed`
- Runtime summary: `Failures: 0`
- C6 suite: `C6 playfeel: 24 / 0 failures`

## MGSF dogfood

Factory CI run `36438711683` executed:

```text
catalog ok: 5 services
service=playtest-report findings=1 eval=PASS
dogfood=playtest-report findings=1 eval=PASS
8 passed in 0.05s
```

The bridged C6 near-miss emitted one medium-severity finding with source event traceability preserved.

## Evidence interpretation

The Godot runtime result and C6 assertions are real-project evidence.

The bridge values for confusion and surprise are deterministic model values, explicitly labeled `deterministic_model_not_human_measurement`. They are not represented as human measurements.
