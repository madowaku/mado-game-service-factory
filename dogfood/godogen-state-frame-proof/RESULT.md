# MGSF-M0.9.2 State-to-frame dogfood evidence

Date: 2026-10-15 (JST)

## Verified real-engine image measurement

- Workflow: https://github.com/madowaku/mado-game-service-factory/actions/runs/38678600825
- The Godot 4.7.2 .NET C# GYRO scene was executed under Xvfb.
- Scripted input-to-state proof: runtime PASS, three state checks PASS.
- Independent FFmpeg movie frame measurement: PASS at five timestamps (5/5).
- Per-probe measured RGB centroid vs state pixel position and video/trace SHA-256 are in frame-proof.json.
- All 22 focused M0.9.1/M0.9.2 verifier tests passed in the same real-engine workflow.
- The video, state trace, runner and frame-proof are uploaded in the GitHub Actions artifact.

## Regression CI

- MGSF suite: https://github.com/madowaku/mado-game-service-factory/actions/runs/38678810356
- 57 pytest tests passed, 13 services validated, original Godot Capture still PASS.

## What is and isn't demonstrated

This is an **actual Godot engine + decoded real movie pixels**, with color
tracking independently calculated from frames. The scene source is the
hand-authored GYRO verification fixture. This is not a sample created by
Godogen or Codex, and the autonomy status is **HOLD**.

The M0.9.2 opt-in generation runner, source fingerprints, generated-game
recapture and cross-run gate are now implemented and contract-tested, but
have NOT been executed against an authenticated, truly Codex-generated game
in this run. No AI-produced game artifacts or paid API usages are claimed.

Status: pixel/state proof PASS; Godogen autonomous generation HOLD; service incubation.
