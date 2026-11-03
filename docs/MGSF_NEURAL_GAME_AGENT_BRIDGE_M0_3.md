# MGSF-WSP-M0.3: Neural Game Agent Bridge

**Stage:** incubation  
**Evidence scope:** actual Godot runtime of a self-contained minimal grid game; NOT a shipping game  
**Promotion gate:** HOLD even if engine verification succeeds

## Goal

Turn the M0.2 `godot-handoff.json` from an unexecuted integration contract into an actual, inspectable **Godot game runtime** with proof that policy decisions and rendered frames originated from the engine. Do not silently treat synthetic Python frames or agent descriptions as gameplay captures.

```text
M0.2 held-out 25-to-5 policy + scenarios
     |  JSON / SHA-256
     v
Godot 4 fixture (bridge.gd)          Python independent M0.2 policy oracle
     |                                     |
     +-- choose actions each turn          +-- compute expected action/logits
     +-- modify 2D game board              +-- compute expected coordinates
     +-- render via viewport               +-- compute expected outcomes
     +-- save 2 direct PNGs                 |
     +-- write Godot JSON trace             |
     |                                     |
     +-------------- trace parity validator + PNG/header/hash checks
                                            |
                                            v
                                   MGSF Evidence Bundle
                                   runtime PASS / promotion HOLD
```

## How to run

Install Godot 4.x locally and the MGSF Python package (3.11+). No API keys, cloud inference, neural training, or GPU cluster are required. On Linux a graphical framebuffer is required; CI uses Xvfb.

```bash
python -m pip install -e '.[dev]'
mgsf neural-behavior-eval fixtures/weight-space/gridworld-v1.json --seed 20261103 --count 40 --output-root evidence/neural-behavior
mgsf godot-neural-bridge evidence/neural-behavior/godot-handoff.json \
  --project fixtures/godot-neural-bridge --godot /path/to/godot \
  --xvfb --count 6 --output-root evidence
pytest -q tests/test_godot_neural_bridge.py
```

Remove `--xvfb` on Windows or environments with a working display server.

## Artifacts

Output folder: `evidence/godot-neural-bridge/`.

| Path | Provenance |
|---|---|
| `godot-trace.json` | Written by the Godot scene after executing the input policy and grid rules |
| `before.png`, `after.png` | Saved by Godot from the live scene viewport using `get_viewport().get_texture().get_image().save_png(...)` |
| `godot-version.log` | Actual engine executable version invocation |
| `godot-preflight.log` | Godot editor import/parse preflight |
| `godot-runtime.log` | Captured Godot process output, return code and completion marker |
| `godot-neural-bridge-evidence.json` | Python validation results, source hashes, artifact hashes, matched episodes, and conditional PASS/FAIL |

Python checks each **Godot** action, destination, selected index, all five output logits (within `1e-6`), winner, episode outcome and step count against an independently computed Python execution of the **same policy and same rules**. An absent runtime, malformed/unverifiable frame, nonzero engine exit, changed handoff, missing log, or trace divergence yields runtime **FAIL**. Stale screenshots and traces are removed before each run.

The real engine and direct viewport frames are proven only to the extent of the preserved runner log and hashed artifacts. This does **not** prove the policy was actually driven by keyboard/controller input, a real user played it, or the policy will work in a different Godot project.

## The two gates

- `status=PASS`: an actual **Godot standalone fixture** executed and matched the Python oracle, with two distinct captured PNGs and verifiable source/log hashes.
- `promotion_gate.status=HOLD`: remains unconditionally HOLD; no authored production game was integrated, no external independent gameplay/behavior benchmark, and no player experience was measured.

The Godot source only reads the explicit file paths provided by the MGSF runner, does not upload data, and does not deploy games. CI keeps its artifacts for review. This is a stacked Draft PR on M0.2; first review and merge M0.1, then M0.2, then this M0.3 when appropriate.

## Next

Implement a reviewed adapter for one **existing** authored Godot project, preserving script/scene version hashes, inputs, engine frames and action traces. Add independent scenarios and a small non-neural planner baseline before making claims about gameplay intelligence.
