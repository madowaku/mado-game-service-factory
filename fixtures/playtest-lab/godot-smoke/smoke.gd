extends Node2D

var progress := 0.0

func _process(_delta: float) -> void:
    if Input.is_action_pressed("ui_right"):
        progress += 1.0

func mgsf_playtest_state() -> Dictionary:
    return {"progress": progress, "won": progress >= 4.0, "deaths": 0, "retries": 0}
