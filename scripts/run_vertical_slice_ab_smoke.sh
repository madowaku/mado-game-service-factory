#!/usr/bin/env bash
# Real Godot paired harness smoke; identical source DOES NOT test skill efficacy.
set -euo pipefail
GODOT="$1"
OUTPUT="$(mkdir -p "$2" && cd "$2" && pwd)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM="$ROOT/vendor/vertical-slice"
BASELINE="f0514229d7f2036ec25646d09e3647c8d870dadb"
test -f "$UPSTREAM/project.godot"
for arm in control treatment; do
  WORKTREE="$OUTPUT/worktrees/$arm"
  mkdir -p "$(dirname "$WORKTREE")"
  git clone --quiet "$UPSTREAM" "$WORKTREE"
  git -C "$WORKTREE" checkout --quiet --detach "$BASELINE"
  test "$(git -C "$WORKTREE" rev-parse HEAD)" = "$BASELINE"
  cp "$ROOT/fixtures/agent-skills/vertical-slice-ab-scenario.gd" "$WORKTREE/tests/ab_scenario.gd"
  git -C "$WORKTREE" config user.name "MGSF neutral dogfood fixture"
  git -C "$WORKTREE" config user.email "ci-fixture@mgsf.invalid"
  # Godot 4.7 generates *.gd.uid imports. Freeze these BEFORE capture and
  # test-run provenance checks; never weaken the clean-commit requirement.
  "$GODOT" --headless --editor --path "$WORKTREE" --quit-after 1 >/dev/null
  git -C "$WORKTREE" add -A
  git -C "$WORKTREE" commit --quiet -m "test: freeze independent MGSF C6 A/B assertions"
  test -z "$(git -C "$WORKTREE" status --porcelain)"
done

mgsf skill-route "$ROOT/fixtures/agent-skills/vertical-slice-testing-request.json" \
  --output-root "$OUTPUT/routing"
ROUTE="$OUTPUT/routing/vertical-slice-c6-testing-m092/skill-route.json"
grep -q '"selected_skill": "godot-testing-patterns"' "$ROUTE"
mgsf skill-ab-plan "$ROOT/fixtures/agent-skills/vertical-slice-c6-ab.json" \
  "$ROUTE" --output-root "$OUTPUT/plan"
PLAN="$OUTPUT/plan/vertical-slice-c6-ab-001/experiment.json"

for arm in control treatment; do
  mgsf godot-capture "$OUTPUT/worktrees/$arm" --godot "$GODOT" --xvfb \
    --output-root "$OUTPUT/capture-$arm"
done

mgsf skill-ab-run "$PLAN" "$OUTPUT/worktrees/control" "$OUTPUT/worktrees/treatment" \
  --godot "$GODOT" \
  --control-capture-eval "$OUTPUT/capture-control/godot-capture-adapter/vertical-slice-c6-direct/adapter_eval.json" \
  --treatment-capture-eval "$OUTPUT/capture-treatment/godot-capture-adapter/vertical-slice-c6-direct/adapter_eval.json" \
  --output-root "$OUTPUT/benchmark"

RESULT="$OUTPUT/benchmark/vertical-slice-c6-ab-001/benchmark.json"
python - "$RESULT" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as stream:
    data = json.load(stream)
assert data["status"] == "REVIEW", data
assert data["evidence_class"] == "paired_godot_runner_evidence", data
assert data["verdict"] == "TIED_ON_ASSERTIONS", data
assert data["paired_pass_delta"] == 0, data
assert data["promotion_status"] == "HOLD", data
for arm in ("control", "treatment"):
    record = data["arms"][arm]
    assert record["capture_verified"], record
    assert record["engine_returncode"] == 0, record
    assert record["passed_assertions"] == 3, record
print("MGSF_NEUTRAL_PAIRED_ENGINE_PROOF=PASS")
print("MGSF_SKILL_EFFECTIVENESS=NOT_TESTED")
PY

for arm in control treatment; do
  printf '{"schema_version":1,"runner":"fixture-not-codex","arm":"%s"}\n' "$arm" > "$OUTPUT/$arm-fixture-receipt.json"
done

mgsf skill-dogfood-eval "$PLAN" "$ROUTE" "$RESULT" \
  "$OUTPUT/control-fixture-receipt.json" "$OUTPUT/treatment-fixture-receipt.json" \
  --output-root "$OUTPUT/dogfood"

DOGFOOD="$OUTPUT/dogfood/vertical-slice-c6-ab-001/dogfood-evidence.json"
python - "$DOGFOOD" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as stream:
    data = json.load(stream)
assert data["status"] == "HOLD", data
assert data["promotion_status"] == "HOLD", data
assert data["causal_claim_supported"] is False, data
assert "control: invalid receipt runner" in data["blockers"], data
print("MGSF_SKILL_DOGFOOD_NEGATIVE_GATE=PASS")
PY
