extends Node2D
class_name MGSFPixelVolumeStack

## Horizontal sheet: leftmost cell is z=0 (ground); rightmost is top.
@export var sprite_sheet: Texture2D
@export_range(1, 64) var layers: int = 12
@export_range(0.1, 1.0) var vertical_squash: float = 0.75
@export_range(0.0, 4.0) var layer_spacing: float = 1.0
@export var angular_velocity: float = 0.55
var yaw: float = 0.0

func _process(delta: float) -> void:
    yaw = fposmod(yaw + delta * angular_velocity, TAU)
    queue_redraw()

func _draw() -> void:
    if sprite_sheet == null or layers < 1:
        return
    var source_width: int = sprite_sheet.get_width()
    if source_width % layers != 0:
        return
    var cw: int = int(source_width / layers)
    var ch: int = sprite_sheet.get_height()
    var target: Rect2 = Rect2(-floorf(cw / 2.0), -floorf(ch / 2.0), cw, ch)
    var rotation_basis: Transform2D = Transform2D(yaw, Vector2.ZERO)
    for layer in range(layers):
        var height_offset: float = -roundf(layer * layer_spacing)
        var projection: Transform2D = Transform2D(
            Vector2.RIGHT, Vector2(0.0, vertical_squash), Vector2(0.0, height_offset))
        draw_set_transform_matrix(projection * rotation_basis)
        draw_texture_rect_region(sprite_sheet, target, Rect2(layer * cw, 0, cw, ch))
    draw_set_transform_matrix(Transform2D.IDENTITY)
