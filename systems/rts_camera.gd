class_name RtsCamera
extends Camera3D

## Warcraft 3 style follow camera: fixed pitch, fixed yaw, no roll, no player control.
##
## Warcraft 3's game camera is perspective, not orthographic — the isometric feel
## comes from the fixed steep angle rather than the projection. Its defaults are
## distance 1650, angle of attack 304, FoV 70, rotation 90. In that scale 270 is
## straight down, so 304 works out to 56 degrees below horizontal, and rotation 90
## means axis-aligned (no diagonal yaw). Scaled to metres that distance is ~26 m,
## which makes a 1.8 m capsule unreadably small, so we default closer and narrower.
##
## Must live beside the player in the level, never as a child of it — the knight
## rotates to face his travel direction and would drag a child camera around with him.

@export var target: Node3D

## 26.0 is the Warcraft 3 faithful value; 18.0 frames a human-sized character better.
@export var distance: float = 18.0
@export_range(0.0, 89.0) var pitch_degrees: float = 56.0
@export var yaw_degrees: float = 0.0
## Aim at the chest rather than the feet, so the character sits mid-frame.
@export var height_offset: float = 1.0
@export var follow_speed: float = 8.0


func _ready() -> void:
	fov = 60.0
	snap_to_target()


## Jump straight to the framed position, skipping the follow smoothing. Call this
## after assigning `target` from a parent's _ready(), which runs after this one —
## otherwise the camera visibly slides in from the world origin on the first frames.
func snap_to_target() -> void:
	if target:
		global_position = _desired_position(target.global_position)
	_apply_rotation()


func _process(delta: float) -> void:
	if target == null:
		return
	# Follow is visual, so it belongs in _process. Exponential smoothing rather
	# than lerp(x, y, speed * delta) keeps the feel identical at any framerate.
	var weight := 1.0 - exp(-follow_speed * delta)
	global_position = global_position.lerp(_desired_position(target.global_position), weight)
	_apply_rotation()


func _desired_position(focus: Vector3) -> Vector3:
	var pitch := deg_to_rad(pitch_degrees)
	var offset := Vector3(0.0, sin(pitch), cos(pitch)) * distance
	return focus + Vector3.UP * height_offset + Basis(Vector3.UP, deg_to_rad(yaw_degrees)) * offset


func _apply_rotation() -> void:
	# Set the angle directly instead of look_at(): the framing stays rock steady
	# while the position smooths, with no wobble as the target moves.
	rotation = Vector3(-deg_to_rad(pitch_degrees), deg_to_rad(yaw_degrees), 0.0)
