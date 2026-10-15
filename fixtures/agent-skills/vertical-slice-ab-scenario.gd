# MGSF-M0.9.2: independent, frozen game-state test scenario for both A/B arms.
# Deliberately evaluates actual existing Godot suites. Not a print-only fixture.
extends SceneTree


const SUITES = {
	"playfeel": preload("res://tests/test_c6_playfeel.gd"),
	"blind_privacy": preload("res://tests/test_projection_safety.gd"),
	"sensor_logic": preload("res://tests/test_sensor_logic.gd"),
}


func _initialize() -> void:
	call_deferred("_run_scenario")


func _run_scenario() -> void:
	var args := OS.get_cmdline_user_args()
	var seed_arg := ""
	for arg in args:
		if arg.begins_with("--mgsf-seed="):
			if not seed_arg.is_empty():
				push_error("Repeated MGSF seed argument")
				quit(1)
				return
			seed_arg = arg.trim_prefix("--mgsf-seed=")
	if not seed_arg.is_valid_int():
		push_error("MGSF seed is missing or invalid")
		quit(1)
		return

	var test_seed := int(seed_arg)
	if test_seed < 0 or test_seed > 2147483647:
		push_error("MGSF seed is outside the permitted range")
		quit(1)
		return
	seed(test_seed)
	print("MGSF_SEED:%d" % test_seed)
	var any_failure := false
	for assertion_id in ["playfeel", "blind_privacy", "sensor_logic"]:
		var suite := (SUITES[assertion_id] as Script).new()
		var result: Dictionary = suite.run()
		var suite_ok := result.has("failures") and (result["failures"] as Array).is_empty() \
			and result.has("passed") and int(result["passed"]) > 0
		print("MGSF_ASSERT:%s:%s" % [assertion_id, "PASS" if suite_ok else "FAIL"])
		if not suite_ok:
			any_failure = true
			for finding in result.get("failures", []):
				push_error("%s: %s" % [assertion_id, str(finding)])
		suite = null
	quit(1 if any_failure else 0)
