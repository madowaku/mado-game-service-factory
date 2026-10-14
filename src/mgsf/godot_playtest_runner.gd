extends SceneTree

# Opt-in replay runner. The target scene must expose mgsf_playtest_state()
# on the scene-relative node named in the scenario.
func _initialize() -> void:
    call_deferred("_run")


func _fail(message: String) -> void:
    push_error("MGSF_PLAYTEST_ERROR: " + message)
    quit(1)


func _run() -> void:
    var scenario_path := OS.get_environment("MGSF_PLAYTEST_SCENARIO")
    var trace_path := OS.get_environment("MGSF_PLAYTEST_TRACE")
    if scenario_path.is_empty() or trace_path.is_empty():
        _fail("missing runner environment")
        return
    if not FileAccess.file_exists(scenario_path):
        _fail("scenario file missing")
        return
    var scenario: Variant = JSON.parse_string(FileAccess.get_file_as_string(scenario_path))
    if not (scenario is Dictionary):
        _fail("invalid scenario JSON")
        return
    var packed: Variant = load(str(scenario.get("scene", "")))
    if not (packed is PackedScene):
        _fail("scene is not a PackedScene")
        return
    var scene_root: Node = packed.instantiate()
    get_root().add_child(scene_root)
    current_scene = scene_root
    await process_frame
    var observer: Node = scene_root.get_node_or_null(NodePath(str(scenario.get("state_node", "."))))
    if observer == null or not observer.has_method("mgsf_playtest_state"):
        _fail("state_node must implement mgsf_playtest_state()")
        return
    var file := FileAccess.open(trace_path, FileAccess.WRITE)
    if file == null:
        _fail("unable to write trace")
        return
    var steps: Array = scenario.get("steps", [])
    for step_index in range(steps.size()):
        var step: Dictionary = steps[step_index]
        var action: String = str(step.get("action", ""))
        var frames: int = int(step.get("frames", 0))
        if not InputMap.has_action(action) or frames < 1 or frames > 600:
            file.close()
            _fail("invalid action or frame count: " + action)
            return
        var press := InputEventAction.new()
        press.action = action
        press.pressed = true
        Input.parse_input_event(press)
        for frame in range(frames):
            await process_frame
        var release := InputEventAction.new()
        release.action = action
        release.pressed = false
        Input.parse_input_event(release)
        await process_frame
        var observed: Variant = observer.call("mgsf_playtest_state")
        if not (observed is Dictionary):
            file.close()
            _fail("mgsf_playtest_state() must return Dictionary")
            return
        var row := {
            "step": step_index,
            "action": action,
            "frames": frames,
            "state": observed,
            "errors": [],
        }
        file.store_line(JSON.stringify(row))
    file.close()
    print("MGSF_PLAYTEST_OK")
    quit(0)
