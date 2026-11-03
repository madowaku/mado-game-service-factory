extends Node2D
## A real Godot scene that executes the portable M0.2 policy and renders its own board.
## It is an isolated game fixture, NOT evidence of integration with any shipped title.

const ACTIONS := ["noop", "up", "down", "left", "right"]
const DELTAS := [Vector2i(0, 0), Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]
const FEATURES := ["goal_progress", "hazard", "wall", "visited", "noop"]

var board_size: int = 5
var agent: Vector2i = Vector2i.ZERO
var target: Vector2i = Vector2i(4, 4)
var hazard: Vector2i = Vector2i(2, 2)
var current_step: int = 0
var display_status: String = "ready"


func _fail(reason: String) -> void:
    push_error("MGSF_NEURAL_BRIDGE_FAIL: " + reason)
    get_tree().quit(2)


func _at(value: Array) -> Vector2i:
    return Vector2i(int(value[0]), int(value[1]))


func _distance(a: Vector2i, b: Vector2i) -> int:
    return absi(a.x - b.x) + absi(a.y - b.y)


func _visited_key(pos: Vector2i) -> String:
    return "%d,%d" % [pos.x, pos.y]


func _features(visited: Dictionary) -> Array:
    var feature_values: Array = []
    for i in range(ACTIONS.size()):
        var destination: Vector2i = agent + DELTAS[i]
        var blocked: bool = destination.x < 0 or destination.y < 0 or destination.x >= board_size or destination.y >= board_size
        if blocked:
            destination = agent
        feature_values.append(float(_distance(agent, target) - _distance(destination, target)))
        feature_values.append(float(int(destination == hazard)))
        feature_values.append(float(int(blocked)))
        feature_values.append(float(int(visited.has(_visited_key(destination)))))
        feature_values.append(float(int(i == 0)))
    return feature_values


func _decision(policy: Dictionary, visited: Dictionary) -> Dictionary:
    var input_values: Array = _features(visited)
    var weights: Array = policy["weights"]
    var biases: Array = policy["bias"]
    var scores: Array = []
    var winner_index: int = 0
    var best: float = -INF
    for i in range(ACTIONS.size()):
        var logit: float = 0.0
        var row: Array = weights[i]
        for col in range(input_values.size()):
            logit += float(row[col]) * float(input_values[col])
        logit += float(biases[i])
        scores.append(logit)
        if logit > best:
            best = logit
            winner_index = i
    return {"winner": ACTIONS[winner_index], "winner_index": winner_index, "logits": scores}


func _simulate(episode: Dictionary, policy: Dictionary) -> Dictionary:
    board_size = int(episode["size"])
    agent = _at(episode["start"])
    target = _at(episode["goal"])
    hazard = _at(episode["hazard"])
    display_status = "playing"
    current_step = 0
    var visited: Dictionary = {}
    visited[_visited_key(agent)] = true
    var events: Array = []
    var outcome: String = "timeout"
    for step in range(1, int(episode["max_steps"]) + 1):
        var decision: Dictionary = _decision(policy, visited)
        var index: int = int(decision["winner_index"])
        var previous: Vector2i = agent
        var candidate: Vector2i = agent + DELTAS[index]
        var wall: bool = candidate.x < 0 or candidate.y < 0 or candidate.x >= board_size or candidate.y >= board_size
        if wall:
            candidate = agent
        agent = candidate
        visited[_visited_key(agent)] = true
        current_step = step
        events.append({
            "step": step,
            "from": [previous.x, previous.y],
            "to": [agent.x, agent.y],
            "wall": wall,
            "decision": decision,
        })
        if agent == hazard:
            outcome = "hazard"
            break
        if agent == target:
            outcome = "success"
            break
    display_status = outcome
    return {
        "scenario_id": str(episode["id"]),
        "outcome": outcome,
        "steps": events.size(),
        "trace": events,
    }


func _screenshot(path: String) -> bool:
    queue_redraw()
    await RenderingServer.frame_post_draw
    var screenshot: Image = get_viewport().get_texture().get_image()
    if screenshot.is_empty():
        return false
    return screenshot.save_png(path) == OK


func _write_json(path: String, value: Dictionary) -> bool:
    var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        return false
    file.store_string(JSON.stringify(value, "  ") + "\n")
    file.close()
    return true


func _ready() -> void:
    var handoff_path: String = OS.get_environment("MGSF_BRIDGE_HANDOFF")
    var output_dir: String = OS.get_environment("MGSF_BRIDGE_OUTPUT")
    var limit_value: String = OS.get_environment("MGSF_BRIDGE_CASES")
    if handoff_path.is_empty() or output_dir.is_empty() or limit_value.is_empty():
        _fail("required environment values missing")
        return
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(handoff_path))
    if not (parsed is Dictionary):
        _fail("handoff JSON not a dictionary")
        return
    var handoff: Dictionary = parsed
    if handoff.get("schema_version") != 1 or handoff.get("contract_kind") != "godot_gridworld_handoff":
        _fail("unsupported handoff")
        return
    var all_episodes: Array = handoff.get("episodes", [])
    var policy: Dictionary = handoff.get("policy", {})
    var wanted: int = int(limit_value)
    if wanted <= 0 or wanted > all_episodes.size() or policy.get("architecture") != "linear_25_to_5":
        _fail("invalid case count or policy architecture")
        return
    var records: Array = []
    for i in range(wanted):
        var episode: Dictionary = all_episodes[i]
        if i == 0:
            board_size = int(episode["size"])
            agent = _at(episode["start"])
            target = _at(episode["goal"])
            hazard = _at(episode["hazard"])
            display_status = "initial"
            current_step = 0
            if not (await _screenshot(output_dir.path_join("before.png"))):
                _fail("could not capture before.png from Godot viewport")
                return
        var result: Dictionary = _simulate(episode, policy)
        records.append(result)
        if i == 0:
            if not (await _screenshot(output_dir.path_join("after.png"))):
                _fail("could not capture after.png from Godot viewport")
                return
    var evidence: Dictionary = {
        "schema_version": 1,
        "engine": "Godot",
        "execution_status": "completed",
        "source_handoff_sha256": FileAccess.get_sha256(handoff_path),
        "episodes": records,
        "frame_sources": ["before.png", "after.png"],
    }
    if not _write_json(output_dir.path_join("godot-trace.json"), evidence):
        _fail("could not write Godot trace")
        return
    print("MGSF_NEURAL_BRIDGE_OK episodes=%d" % records.size())
    get_tree().quit(0)


func _draw() -> void:
    draw_rect(Rect2(0, 0, 640, 640), Color("#0e1624"))
    draw_string(ThemeDB.fallback_font, Vector2(32, 49), "MGSF / NEURAL AGENT", HORIZONTAL_ALIGNMENT_LEFT, -1, 25, Color("#dbf0ff"))
    draw_string(ThemeDB.fallback_font, Vector2(32, 79), "Godot runtime | step %d | %s" % [current_step, display_status], HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("#8ac7f1"))
    var tile_size: float = minf(64.0, 462.0 / float(board_size))
    var start: Vector2 = Vector2((640.0 - float(board_size) * tile_size) * 0.5, 115.0)
    for y in range(board_size):
        for x in range(board_size):
            var cell: Vector2i = Vector2i(x, y)
            var area: Rect2 = Rect2(start + Vector2(x, y) * tile_size, Vector2.ONE * (tile_size - 3.0))
            var shade: Color = Color("#1d3048") if (x + y) % 2 == 0 else Color("#263b55")
            if cell == target:
                shade = Color("#227b66")
            if cell == hazard:
                shade = Color("#a34d58")
            draw_rect(area, shade, true)
            if cell == agent:
                draw_circle(area.get_center(), tile_size * 0.27, Color("#ffc96f"))
                draw_arc(area.get_center(), tile_size * 0.29, 0, TAU, 32, Color("#ffe6ad"), 2.0)
    draw_string(ThemeDB.fallback_font, Vector2(33, 599), "Yellow: agent   |   Green: goal   |   Red: hazard", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("#afc0d5"))
