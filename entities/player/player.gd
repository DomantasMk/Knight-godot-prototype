extends CharacterBody3D

## The knight. WASD moves relative to the camera, the body turns to face the
## direction of travel, LMB swings a forward arc that damages whatever is inside
## the Hitbox at the moment of impact, and Space rolls.
##
## Gameplay state is the State enum below. The AnimationTree runs its own state
## machine in parallel and is only ever *told* which state to show - it never
## decides anything. Four states keep the enum form the right call; revisit if
## this grows past ~5 or the states start needing real enter/exit logic.

enum State { IDLE, RUN, ATTACK, ROLL }

## Clip name per gameplay state. The AnimationTree's states are named to match.
const ANIM_NAMES := {
	State.IDLE: &"idle",
	State.RUN: &"run",
	State.ATTACK: &"attack",
	State.ROLL: &"roll",
}

@export var move_speed: float = 6.0
@export var acceleration: float = 40.0
@export var friction: float = 50.0
@export var turn_speed: float = 12.0
@export var attack_cooldown: float = 0.45
## How long the Attack state holds input. Match this to the attack clip's length.
@export var attack_duration: float = 0.5
## Movement speed multiplier while a swing is playing.
@export var attack_move_penalty: float = 0.35
@export var roll_speed: float = 11.0
@export var roll_duration: float = 0.7
@export var roll_cooldown: float = 0.8

@onready var _hitbox: HitboxComponent = %Hitbox

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")
var _camera: Camera3D
var _state: State = State.IDLE
var _state_time: float = 0.0
var _attack_cooldown_left: float = 0.0
var _roll_cooldown_left: float = 0.0
var _struck: bool = false
var _roll_direction: Vector3 = Vector3.ZERO
## The AnimationTree's own state machine. Told where to go, never asked.
var _playback: AnimationNodeStateMachinePlayback


func _ready() -> void:
	var tree: AnimationTree = %AnimationTree
	_playback = tree.get("parameters/playback") as AnimationNodeStateMachinePlayback
	_playback.travel(ANIM_NAMES[_state])
	EventBus.player_spawned.emit(self)


func _physics_process(delta: float) -> void:
	_attack_cooldown_left = maxf(_attack_cooldown_left - delta, 0.0)
	_roll_cooldown_left = maxf(_roll_cooldown_left - delta, 0.0)
	_state_time += delta

	if not is_on_floor():
		velocity.y -= _gravity * delta

	var direction := _movement_direction()
	_advance_state(direction)

	match _state:
		State.ATTACK:
			_drive_ground(direction, move_speed * attack_move_penalty, delta)
		State.ROLL:
			_drive_roll()
		_:
			_drive_ground(direction, move_speed, delta)

	move_and_slide()


## Every transition lives here; each state decides only what may follow it.
## Attack and Roll are locked - they ignore input until their timer expires.
func _advance_state(direction: Vector3) -> void:
	var next := _state

	match _state:
		State.ATTACK:
			if _state_time >= attack_duration:
				next = _ground_state(direction)
		State.ROLL:
			if _state_time >= roll_duration:
				next = _ground_state(direction)
		_:
			if Input.is_action_just_pressed("dodge") and _roll_cooldown_left <= 0.0:
				next = State.ROLL
			elif Input.is_action_just_pressed("attack") and _attack_cooldown_left <= 0.0:
				next = State.ATTACK
			else:
				next = _ground_state(direction)

	if next != _state:
		_enter_state(next, direction)


func _ground_state(direction: Vector3) -> State:
	return State.RUN if direction != Vector3.ZERO else State.IDLE


func _enter_state(next: State, direction: Vector3) -> void:
	_state = next
	_state_time = 0.0

	match next:
		State.ATTACK:
			_attack_cooldown_left = attack_cooldown
			_struck = false
		State.ROLL:
			_roll_cooldown_left = roll_cooldown
			# Commit to one direction for the whole roll; input during it is ignored.
			# With no input, roll the way the body already faces.
			var heading := direction if direction != Vector3.ZERO else -global_transform.basis.z
			heading.y = 0.0
			_roll_direction = heading.normalized()
			# Snap rather than turn: the clip is in-place, so a roll that travels
			# sideways while the body still faces forward reads as a slide.
			rotation.y = _yaw_for(_roll_direction)

	_playback.travel(ANIM_NAMES[next])


## Steer only the horizontal plane so gravity on velocity.y survives intact.
func _drive_ground(direction: Vector3, speed: float, delta: float) -> void:
	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	if direction != Vector3.ZERO:
		horizontal = horizontal.move_toward(direction * speed, acceleration * delta)
		_face(direction, delta)
	else:
		horizontal = horizontal.move_toward(Vector3.ZERO, friction * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z


func _drive_roll() -> void:
	# Taper so the roll settles instead of stopping dead on its last frame.
	var t := clampf(_state_time / roll_duration, 0.0, 1.0)
	var speed := roll_speed * (1.0 - t * t)
	velocity.x = _roll_direction.x * speed
	velocity.z = _roll_direction.z * speed


## Lands the swing. Called by the Call Method track on the attack clip, at frame 8
## of 15 - the frame where the blade is out front and its tip is inside the Hitbox.
## The track is attached at import time by tools/import/knight_rigged_import.gd, and
## resolves this node by path, so the name has to stay public and stay put.
## Guarded because a blend that re-enters the clip would otherwise strike twice.
func deal_attack_damage() -> void:
	if _struck:
		return
	_struck = true
	_hitbox.strike()


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
	rotation.y = lerp_angle(rotation.y, _yaw_for(direction), 1.0 - exp(-turn_speed * delta))


## A Node3D's forward is -Z, so the target yaw negates both components.
func _yaw_for(direction: Vector3) -> float:
	return atan2(-direction.x, -direction.z)
