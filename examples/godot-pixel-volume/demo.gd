extends Node2D

const StackScene = preload("res://stack_sprite.gd")
const FILES: Array[String] = ["toy-car", "tree", "paper-house"]
const X_COORDS: Array[int] = [60, 160, 270]

func _ready() -> void:
    for i in FILES.size():
        var base: String = "res://generated/" + FILES[i]
        var manifest_file: FileAccess = FileAccess.open(base + ".json", FileAccess.READ)
        var image: Image = Image.new()
        if manifest_file == null or image.load(base + ".png") != OK:
            push_warning("Missing asset: run the Python build command in README.md before starting Godot")
            continue
        var metadata: Variant = JSON.parse_string(manifest_file.get_as_text())
        if typeof(metadata) != TYPE_DICTIONARY or not metadata.has("slices"):
            continue
        var stack: MGSFPixelVolumeStack = StackScene.new()
        stack.sprite_sheet = ImageTexture.create_from_image(image)
        stack.layers = int(metadata["slices"])
        stack.angular_velocity = 0.3 + float(i) * 0.23
        stack.position = Vector2(X_COORDS[i], 129)
        add_child(stack)

func _draw() -> void:
    draw_rect(Rect2(0, 138, 320, 42), Color("#243b49"))
    for x in range(0, 320, 16):
        draw_line(Vector2(x, 138), Vector2(x, 180), Color("#3c5e66"))
