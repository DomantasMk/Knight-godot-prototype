extends CharacterBody3D

## Greybox knight. WASD moves relative to the camera, the body turns to face the
## direction of travel, and LMB swings a forward arc that damages whatever is
## inside the Hitbox at the moment of impact.

@export var move_speed: float = 6.0
@export var acceleration: float = 40.0
@export var friction: float = 50.0
@export var turn_speed: float = 12.0
@export var attack_cooldown: float = 0.45
## Gap between the button press and damage landing, so the hit reads mid-arc.
@export var attack_impact_delay: float = 0.12
## Movement speed multiplier while a swing is playing.
@export var attack_move_penalty: float = 0.35

@onready var _weapon_pivot: Node3D = %WeaponPivot
@onready var _hitbox: HitboxComponent = %Hitbox

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")
var _camera: Camera3D
var _cooldown_left: float = 0.0
var _swinging: bool = false
var _swing_tween: Tween


func _ready() -> void:
	EventBus.player_spawned.emit(self)


func _physics_process(delta: float) -> void:
	_cooldown_left = maxf(_cooldown_left - delta, 0.0)

	if not is_on_floor():
		velocity.y -= _gravity * delta

	var direction := _movement_direction()
	var speed := move_speed * (attack_move_penalty if _swinging else 1.0)

	# Steer only the horizontal plane so gravity on velocity.y survives intact.
	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	if direction != Vector3.ZERO:
		horizontal = horizontal.move_toward(direction * speed, acceleration * delta)
		_face(direction, delta)
	else:
		horizontal = horizontal.move_toward(Vector3.ZERO, friction * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z

	move_and_slide()

	if Input.is_action_just_pressed("attack"):
		_try_attack()


## WASD mapped into the camera's frame, flattened onto the ground plane.
func _movement_direction() -> Vector3:
	if _camera == null:
		# The camera is not guaranteed to be current yet during _ready().
		_camera = get_viewport().get_camera_3d()
		if _camera == null:
			return Vector3.ZERO

	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	if input == Vector2.ZERO:
		return Vector3.ZERO

	var cam_basis := _camera.global_transform.basis
	var forward := Vector3(-cam_basis.z.x, 0.0, -cam_basis.z.z).normalized()
	var right := Vector3(cam_basis.x.x, 0.0, cam_basis.x.z).normalized()
	# get_vector() reports y = -1 for move_forward, hence the negation.
	return (right * input.x + forward * -input.y).normalized()


func _face(direction: Vector3, delta: float) -> void:
	# A Node3D's forward is -Z, so the target yaw negates both components.
	var target_yaw := atan2(-direction.x, -direction.z)
	rotation.y = lerp_angle(rotation.y, target_yaw, 1.0 - exp(-turn_speed * delta))


func _try_attack() -> void:
	if _cooldown_left > 0.0:
		return
	_cooldown_left = attack_cooldown
	_swinging = true
	_play_swing()

	await get_tree().create_timer(attack_impact_delay).timeout
	if not is_inside_tree():
		return
	_hitbox.strike()


func _play_swing() -> void:
	# Kill the previous swing first, or spam-clicking stacks tweens on one property.
	if _swing_tween and _swing_tween.is_valid():
		_swing_tween.kill()

	_weapon_pivot.rotation.y = 0.9
	_swing_tween = create_tween()
	_swing_tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_swing_tween.tween_property(_weapon_pivot, "rotation:y", -0.9, 0.2)
	_swing_tween.tween_property(_weapon_pivot, "rotation:y", 0.0, 0.18).set_ease(Tween.EASE_IN_OUT)
	_swing_tween.finished.connect(func() -> void: _swinging = false)
