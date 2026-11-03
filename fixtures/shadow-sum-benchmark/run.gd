extends SceneTree
## MGSF-M0.4: evidence-only runner using SHADOW SUM's unchanged original ShadowRules.
## Executes a disposable Godot kernel that copies the original rules and stage pack.
## The game's original scene/UI is not run and no "solution" field is used.

const ShadowRules = preload("res://src/shadow_rules.gd")
const POLICY_NAMES := ["rule_greedy", "direct_weights"]


func _fail(reason: String) -> void:
    push_error("MGSF_SHADOW_BENCHMARK_FAIL: " + reason)
    quit(2)


func _write_json(path: String, payload: Dictionary) -> bool:
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        return false
    file.store_string(JSON.stringify(payload, "  ") + "\n")
    file.close()
    return true


func _error_score(shadow: Array, clues: Array) -> int:
    var total := 0
    for r in range(5):
        for c in range(5):
            var wanted: int = int(clues[r][c])
            if wanted >= 0:
                total += absi(wanted - int(shadow[r][c]))
    return total


func _evaluate(selection: Dictionary, required: int, clues: Array) -> Dictionary:
    var posts: Array = ShadowRules.make_empty_posts()
    var actions: Array = []
    var plan: Array = selection.get("placements", [])
    if plan.size() != required:
        return {"invalid": "action budget differs from required post count"}
    for entry in plan:
        var cell: Array = entry.get("cell", [])
        if cell.size() != 2:
            return {"invalid": "malformed cell"}
        var r: int = int(cell[0])
        var c: int = int(cell[1])
        if r < 0 or r >= 5 or c < 0 or c >= 5 or posts[r][c]:
            return {"invalid": "out of bounds or duplicate post"}
        posts[r][c] = true
        actions.append([r, c])
    var actual: Array = ShadowRules.compute_shadow(posts)
    var count: int = ShadowRules.count_posts(posts)
    var success: bool = count == required and ShadowRules.matches_visible_clues(actual, clues)
    return {
        "placements": actions,
        "shadow": actual,
        "placed_count": count,
        "success": success,
        "visible_l1_error": _error_score(actual, clues),
    }


func _initialize() -> void:
    var plan_path: String = OS.get_environment("MGSF_SHADOW_PLAN")
    var result_path: String = OS.get_environment("MGSF_SHADOW_RESULT")
    if plan_path.is_empty() or result_path.is_empty():
        _fail("required plan/result environment variables missing")
        return

    var loaded: Variant = JSON.parse_string(FileAccess.get_file_as_string(plan_path))
    if not (loaded is Dictionary):
        _fail("plan must be a JSON object")
        return
    var plan: Dictionary = loaded
    if plan.get("schema_version") != 1 or plan.get("benchmark") != "shadow-sum-authored-rules":
        _fail("unsupported plan")
        return
    if plan.has("solution") or plan.get("solution_fields_exported") != false:
        _fail("plan must contain no stage solutions")
        return
    if plan.get("policies", []) != POLICY_NAMES:
        _fail("unexpected policy names")
        return

    var original_path: String = "res://data/stages_v0_1.json"
    var rules_path: String = "res://src/shadow_rules.gd"
    if FileAccess.get_sha256(original_path) != str(plan.get("source_stage_sha256", "")):
        _fail("authored stage pack source SHA mismatch")
        return
    if FileAccess.get_sha256(rules_path) != str(plan.get("source_rules_sha256", "")):
        _fail("authored rule script source SHA mismatch")
        return

    var raw_stages: Variant = JSON.parse_string(FileAccess.get_file_as_string(original_path))
    if not (raw_stages is Array):
        _fail("authored stages must be an array")
        return
    var authored: Array = raw_stages
    var planned: Array = plan.get("stage_inputs", [])
    if planned.size() != authored.size() or planned.size() != 18:
        _fail("benchmark needs all 18 authored stages")
        return
    var outputs: Array = []
    for index in range(planned.size()):
        var expected: Dictionary = planned[index]
        var stage: Dictionary = authored[index]
        if expected.has("solution") or stage["id"] != expected.get("id"):
            _fail("stage order or plan leakage mismatch")
            return
        var clues: Array = stage["clues"]
        var posts_required: int = int(stage["posts"])
        if clues != expected.get("clues") or posts_required != expected.get("posts"):
            _fail("plan's public stage clues do not match authored source")
            return
        var submitted: Dictionary = expected.get("plans", {})
        var results: Dictionary = {}
        for policy_name in POLICY_NAMES:
            if not submitted.has(policy_name):
                _fail("missing policy " + policy_name)
                return
            var proposal: Dictionary = submitted[policy_name]
            if proposal.get("policy") != policy_name or proposal.get("stage_id") != stage["id"]:
                _fail("policy/stage attribution mismatch")
                return
            var measured: Dictionary = _evaluate(proposal, posts_required, clues)
            if measured.has("invalid"):
                _fail("invalid post action: " + str(measured["invalid"]))
                return
            results[policy_name] = measured
        outputs.append({"id": stage["id"], "policies": results})

    var result: Dictionary = {
        "schema_version": 1,
        "engine": "Godot",
        "kernel": "authored_shadow_sum_rules",
        "source_rules_sha256": FileAccess.get_sha256(rules_path),
        "source_stage_sha256": FileAccess.get_sha256(original_path),
        "stages": outputs,
    }
    if not _write_json(result_path, result):
        _fail("could not write engine results")
        return
    print("MGSF_SHADOW_BENCHMARK_OK stages=%d policies=%d" % [outputs.size(), POLICY_NAMES.size()])
    quit(0)
