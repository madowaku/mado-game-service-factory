# Standalone Godot 4 SceneTree script. Does not edit scenes or audio assets.
# Emits ENGINE STATE ONLY. Headless Dummy cannot prove actual audible output.
extends SceneTree


func _initialize() -> void:
    call_deferred("_probe")


func _probe() -> void:
    var spec_path: String = OS.get_environment("MGSF_SOUND_PROBE_SPEC")
    if spec_path.is_empty() or not FileAccess.file_exists(spec_path):
        push_error("MGSF audio probe spec missing")
        quit(2)
        return
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(spec_path))
    if not parsed is Dictionary:
        push_error("MGSF audio probe spec malformed")
        quit(2)
        return
    var spec: Dictionary = parsed
    var samples: Array = spec.get("tracks", [])
    if samples.is_empty():
        push_error("MGSF audio probe has no tracks")
        quit(2)
        return

    var observations: Array = []
    var previous_sha: String = ""
    var ok: bool = true
    for entry in samples:
        if not entry is Dictionary:
            ok = false
            break
        var path: String = String(entry.get("path", ""))
        var sha: String = String(entry.get("sha256", ""))
        var stream: AudioStreamWAV = AudioStreamWAV.load_from_file(path)
        if stream == null:
            observations.append({"sha256": sha, "load_ok": false, "started": false, "stopped": false, "loop_configured": false, "switched_after": previous_sha, "timestamp_ms": Time.get_ticks_msec()})
            ok = false
            break
        var requested_loop: bool = bool(entry.get("loop_requested", false))
        if requested_loop:
            stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
        var player: AudioStreamPlayer = AudioStreamPlayer.new()
        root.add_child(player)
        player.stream = stream
        player.play()
        await process_frame
        var started: bool = player.playing
        var playback_position: float = player.get_playback_position()
        player.stop()
        await process_frame
        var stopped: bool = not player.playing
        var configured: bool = not requested_loop or stream.loop_mode == AudioStreamWAV.LOOP_FORWARD
        observations.append({"sha256": sha, "load_ok": true, "started": started, "stopped": stopped, "loop_configured": configured, "switched_after": previous_sha, "timestamp_ms": Time.get_ticks_msec(), "playback_position_s": playback_position})
        if not started or not stopped or not configured:
            ok = false
        previous_sha = sha
        player.queue_free()

    var result: Dictionary = {
        "schema": "mgsf.sound_identity.engine_state.v0.3",
        "driver": AudioServer.get_driver_name(),
        "engine_version": Engine.get_version_info().get("string", "unknown"),
        "observations": observations,
        "engine_checks_passed": ok
    }
    var output: FileAccess = FileAccess.open(String(spec.get("result_path", "")), FileAccess.WRITE)
    if output == null:
        push_error("MGSF probe could not write evidence")
        quit(3)
        return
    output.store_string(JSON.stringify(result, "\t") + "\n")
    output.close()
    if ok:
        print("MGSF_SOUND_ENGINE_STATE_OK")
        quit(0)
    else:
        push_error("MGSF sound engine-state check failed")
        quit(4)
