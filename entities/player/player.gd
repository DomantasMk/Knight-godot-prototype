extends CharacterBody3D

## The knight. WASD moves relative to the camera, the body turns to face the
## direction of travel, LMB swings a forward arc that damages whatever is inside
## the Hitbox at the moment of impact, Shift rolls, and Space hops.
##
## Gameplay state is the State enum below. The AnimationTree runs its own state
## machine in parallel and is only ever *told* which state to show - it never
## decides anything. Five states is the ceiling this form was given; the next one
## that needs real enter/exit logic should push the lot into node-based states.

enum State { IDLE, RUN, ATTACK, ROLL, JUMP }

## Clip name per gameplay state. The AnimationTree's states are named to match.
const ANIM_NAMES := {
	State.IDLE: &"idle",
	State.RUN: &"run",
	State.ATTACK: &"attack",
	State.ROLL: &"roll",
	State.JUMP: &"jump",
}

@export var move_speed: float = 6.0
@export var acceleration: float = 40.0
@export var friction: float = 50.0
@export var turn_speed: float = 12.0
@export var attack_cooldown: float = 0.45
## How long the Attack state holds input, in seconds. Deliberately **shorter than the attack
## clip**, and that is the whole point of the constant: the clip's last frames are a recovery
## into an open guard, and the state machine already crossfades them out under whatever comes
## next. Holding input for the full clip animates that recovery twice and spends a fifth of a
## second of responsiveness on nothing.
##
## Set to the overshoot frame - f11 of 18 - which is where the swing reads as finished. The
## impact lands well before it, so cutting here never costs a hit. attack_cooldown still gates
## re-swinging; this only governs when moving, rolling and jumping come back.
@export var attack_lock: float = 11.0 / 30.0
## Movement speed multiplier while a swing is playing.
@export var attack_move_penalty: float = 0.35
@export var roll_speed: float = 11.0
@export var roll_duration: float = 0.7
@export var roll_cooldown: float = 0.8
## Apex of the hop, in metres. Deliberately short: the camera looks down at 56 degrees,
## which foreshortens vertical motion to about half its size on screen, and anything
## taller starts to read as a leap the knight has no business making in armour.
## The measured apex runs ~4 cm over this at 60 Hz - that is what integrating gravity in
## discrete steps costs, not a mistuning, and it scales with the physics tick.
@export var jump_height: float = 0.8
## Multiplies real gravity. 9.8 m/s^2 gives a jump of any readable height an airtime
## near a second, which floats; 1.8x keeps the same 0.8 m arc down to 0.60 s.
## Changing either this or jump_height desyncs the jump clip - see _jump_airtime().
@export var gravity_scale: float = 1.8
## How much of the ground acceleration steers the hop. Air control at 1.0 makes the
## jump a second way to walk; at 0.0 you cannot correct a jump at all.
@export var air_control: float = 0.45

@onready var _hitbox: HitboxComponent = %Hitbox

## Project gravity times gravity_scale, resolved in _ready() rather than here: a variable
## initializer runs before the scene applies its @export values, so folding gravity_scale
## in at this point would quietly ignore anything set in the inspector.
var _gravity: float
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
	_gravity = ProjectSettings.get_setting("physics/3d/default_gravity") * gravity_scale
	var tree: AnimationTree = %AnimationTree
	_playback = tree.get("parameters/playback") as AnimationNodeStateMachinePlayback
	_playback.travel(ANIM_NAMES[_state])
	_check_clips(tree)
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
		State.JUMP:
			_drive_air(direction, delta)
		_:
			_drive_ground(direction, move_speed, delta)

	move_and_slide()


## Every transition lives here; each state decides only what may follow it.
## Attack, Roll and Jump are locked - they ignore input until they release. Roll and Jump
## release when they are done; Attack releases at attack_lock, part-way through its clip.
func _advance_state(direction: Vector3) -> void:
	var next := _state

	match _state:
		State.ATTACK:
			if _state_time >= attack_lock:
				next = _ground_state(direction)
		State.ROLL:
			if _state_time >= roll_duration:
				next = _ground_state(direction)
		State.JUMP:
			# Not a timer: the jump ends when the feet are back down. velocity.y is
			# still positive on the frame the impulse is applied, while is_on_floor()
			# has not been recomputed yet, so testing both needs no takeoff grace.
			if is_on_floor() and velocity.y <= 0.0:
				next = _ground_state(direction)
		_:
			if Input.is_action_just_pressed("dodge") and _roll_cooldown_left <= 0.0:
				next = State.ROLL
			elif Input.is_action_just_pressed("attack") and _attack_cooldown_left <= 0.0:
				next = State.ATTACK
			elif Input.is_action_just_pressed("jump") and is_on_floor():
				next = State.JUMP
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
		State.JUMP:
			# Solved from the height rather than tuned as a velocity, so jump_height
			# means metres and the clip stays in step with the arc through any edit.
			velocity.y = sqrt(2.0 * _gravity * jump_height)

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


## Airborne steering. Two differences from the ground: acceleration is scaled down, and
## there is no friction - releasing the keys mid-hop keeps the momentum you left with
## instead of stopping the knight dead in the air.
func _drive_air(direction: Vector3, delta: float) -> void:
	if direction == Vector3.ZERO:
		return
	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	horizontal = horizontal.move_toward(direction * move_speed,
			acceleration * air_control * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z
	_face(direction, delta)


func _drive_roll() -> void:
	# Taper so the roll settles instead of stopping dead on its last frame.
	var t := clampf(_state_time / roll_duration, 0.0, 1.0)
	var speed := roll_speed * (1.0 - t * t)
	velocity.x = _roll_direction.x * speed
	velocity.z = _roll_direction.z * speed


## Lands the swing. Called by the Call Method track on the attack clip, at frame 8
## of 18 - the contact pose, which the clip's easing also makes the blade's fastest
## frame, with the tip 0.70 m inside the Hitbox. See tools/import/knight_rigged_import.gd
## for why those being the same frame is authored rather than lucky.
## The track is attached at import time by tools/import/knight_rigged_import.gd, and
## resolves this node by path, so the name has to stay public and stay put.
## Guarded because a blend that re-enters the clip would otherwise strike twice.
func deal_attack_damage() -> void:
	if _struck:
		return
	_struck = true
	_hitbox.strike()


## Time from takeoff to touchdown. The jump clip is authored to exactly this, so the
## landing pose arrives on the frame the feet do.
func _jump_airtime() -> float:
	return 2.0 * sqrt(2.0 * jump_height / _gravity)


## Two places where a clip's length and a gameplay number have to agree and nothing in the
## engine makes them. Both are cheap to say out loud and easy to miss by eye, so they are
## warnings at startup rather than comments nobody reads.
func _check_clips(tree: AnimationTree) -> void:
	if not OS.is_debug_build():
		return
	var player := tree.get_node_or_null(tree.anim_player) as AnimationPlayer
	if player == null:
		return

	# Retuning jump_height or gravity_scale would quietly leave the knight touching down in a
	# mid-air pose, or holding the landing squash in the air.
	if player.has_animation(ANIM_NAMES[State.JUMP]):
		var jump_clip: float = player.get_animation(ANIM_NAMES[State.JUMP]).length
		if absf(jump_clip - _jump_airtime()) > 0.08:
			push_warning(("jump clip is %.2fs but the hop lasts %.2fs - retime one to the " +
					"other in tools/rigging/clips_knight.py (JUMP) or in the inspector")
					% [jump_clip, _jump_airtime()])

	# attack_lock ending *before* the clip is the entire point of it. Equal or longer and the
	# recovery is animated twice, which is the bug the constant was introduced to remove.
	if player.has_animation(ANIM_NAMES[State.ATTACK]):
		var attack_clip: float = player.get_animation(ANIM_NAMES[State.ATTACK]).length
		if attack_lock >= attack_clip:
			push_warning(("attack_lock is %.2fs against a %.2fs attack clip - input is held " +
					"for the whole swing, so the clip's recovery tail plays instead of " +
					"crossfading out under the next action") % [attack_lock, attack_clip])


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
