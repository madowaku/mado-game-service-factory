# Godot 4 opt-in Master bus PCM recording for Sound Experience Lab M0.6.
# Copy into a trusted project, register as Autoload "MGSFSoundCapture" MANUALLY.
# Does not start without all MGSF_SOUND_* consent variables.
# Captures engine bus samples, NOT independently verified speaker output.
extends Node

var _effect: AudioEffectCapture
var _effect_index: int = -1
var _active: bool = false
var _pcm: PackedByteArray = PackedByteArray()
var _start_usec: int = 0
var _deadline_usec: int = 0
var _rate: int = 0
var _dest: String = ""
var _markers: Array[Dictionary] = []
var _marker_ids: Dictionary = {}
var _driver: String = ""


func _ready() -> void:
    if OS.get_environment("MGSF_SOUND_CAPTURE_CONSENT") != "YES":
        return
    if not OS.has_environment("MGSF_SOUND_CAPTURE_DIR"):
        return
    _dest = OS.get_environment("MGSF_SOUND_CAPTURE_DIR")
    if not _dest.is_absolute_path():
        push_error("MGSF capture path must be absolute")
        return
    var project_dir: String = ProjectSettings.globalize_path("res://").simplify_path()
    if _dest.simplify_path().begins_with(project_dir):
        push_error("MGSF capture dir must be outside project")
        return
    if FileAccess.file_exists(_dest.path_join("master-bus.wav")) or FileAccess.file_exists(_dest.path_join("capture-manifest.json")):
        push_error("MGSF capture refuses overwrite")
        return
    _driver = AudioServer.get_driver_name()
    if _driver.to_lower() == "dummy" or _driver.is_empty():
        push_warning("MGSF capture unavailable with Dummy audio driver")
        return
    _rate = int(AudioServer.get_mix_rate())
    if _rate < 8000 or _rate > 96000:
        push_error("MGSF capture sample rate unsupported")
        return
    var duration: int = clampi(int(OS.get_environment("MGSF_SOUND_CAPTURE_DURATION_MS")), 500, 10000)
    _effect = AudioEffectCapture.new()
    _effect.buffer_length = 2.0
    _effect_index = AudioServer.get_bus_effect_count(0)
    AudioServer.add_bus_effect(0, _effect)
    _start_usec = Time.get_ticks_usec()
    _deadline_usec = _start_usec + duration * 1000
    _active = true


# Gameplay may call this immediately after an input/scene/audio transition.
# Marks use the same process monotonic timebase as the capture start tick.
func mark_event(marker_id: String, kind: String) -> void:
    if not _active or marker_id.is_empty() or _marker_ids.has(marker_id):
        return
    if not kind in ["start", "switch", "stop", "loop", "input"]:
        return
    _marker_ids[marker_id] = true
    _markers.append({"marker_id": marker_id, "kind": kind, "ticks_usec": Time.get_ticks_usec()})


func _process(_delta: float) -> void:
    if not _active:
        return
    _consume()
    if Time.get_ticks_usec() >= _deadline_usec:
        _finish()


func _consume() -> void:
    if _effect == null:
        return
    while _effect.get_frames_available() > 0:
        var count: int = mini(2048, _effect.get_frames_available())
        var frames: PackedVector2Array = _effect.get_buffer(count)
        for frame in frames:
            var left: int = clampi(int(round(frame.x * 32767.0)), -32768, 32767)
            var right: int = clampi(int(round(frame.y * 32767.0)), -32768, 32767)
            _pcm.append(left & 255)
            _pcm.append((left >> 8) & 255)
            _pcm.append(right & 255)
            _pcm.append((right >> 8) & 255)


func _finish() -> void:
    _consume()
    _active = false
    var stopped: int = Time.get_ticks_usec()
    var discarded: int = int(_effect.get_discarded_frames())
    if _effect_index >= 0:
        AudioServer.remove_bus_effect(0, _effect_index)
        _effect_index = -1
    if _pcm.is_empty():
        push_warning("MGSF captured zero frames; no manifest produced")
        return
    if DirAccess.make_dir_recursive_absolute(_dest) != OK:
        push_error("MGSF could not create output directory")
        return
    var wav_path: String = _dest.path_join("master-bus.wav")
    if FileAccess.file_exists(wav_path) or FileAccess.file_exists(_dest.path_join("capture-manifest.json")):
        push_error("MGSF refuses to overwrite capture files")
        return
    var file: FileAccess = FileAccess.open(wav_path, FileAccess.WRITE)
    if file == null:
        push_error("MGSF could not create WAV")
        return
    # PCM16 stereo RIFF/WAVE, little-endian.
    file.big_endian = false
    file.store_buffer("RIFF".to_ascii_buffer())
    file.store_32(36 + _pcm.size())
    file.store_buffer("WAVEfmt ".to_ascii_buffer())
    file.store_32(16)
    file.store_16(1)
    file.store_16(2)
    file.store_32(_rate)
    file.store_32(_rate * 4)
    file.store_16(4)
    file.store_16(16)
    file.store_buffer("data".to_ascii_buffer())
    file.store_32(_pcm.size())
    file.store_buffer(_pcm)
    file.close()
    var payload: Dictionary = {
        "schema": "mgsf.sound_identity.capture_manifest.v0.6",
        "origin": "godot_master_bus_audioeffectcapture",
        "audio_driver": _driver,
        "consent": true,
        "sample_rate": _rate,
        "channels": 2,
        "sample_count": int(_pcm.size() / 4),
        "discarded_frames": discarded,
        "capture_started_ticks_usec": _start_usec,
        "capture_ended_ticks_usec": stopped,
        "recording_sha256": FileAccess.get_sha256(wav_path),
        "markers": _markers
    }
    var out: FileAccess = FileAccess.open(_dest.path_join("capture-manifest.json"), FileAccess.WRITE)
    if out == null:
        push_error("MGSF could not save capture manifest")
        return
    out.store_string(JSON.stringify(payload, "\t") + "\n")
    out.close()
    print("MGSF_SOUND_CAPTURE_SAVED frames=", int(_pcm.size() / 4), " driver=", _driver)
