extends Node3D

## Demo level: a greybox field with a road down the middle and a scattered treeline.
##
## The floor, road, lighting and camera live in the .tscn; the trees are placed here
## at runtime so the scene file stays small and there are no hand-written transforms
## to get wrong. The seed is fixed, so the layout is identical every run.

const TREE_SCENE: PackedScene = preload("res://entities/tree/tree.tscn")

@export var tree_count: int = 26
@export var scatter_seed: int = 1337
## Half-width of the road strip kept clear of trees.
@export var road_half_width: float = 4.5
## Radius around the player's spawn kept clear, so he never starts inside a trunk.
@export var spawn_clearance: float = 4.0
## Trees are scattered within +/- this distance on both ground axes.
@export var field_extent: float = 17.0
## Minimum gap between two trunks.
@export var min_tree_spacing: float = 3.0

@onready var _trees: Node3D = %Trees
@onready var _player: CharacterBody3D = %Player
@onready var _camera: RtsCamera = %RtsCamera


func _ready() -> void:
	GameManager.current_level = scene_file_path

	# Wired here rather than as a NodePath @export: this node's _ready() runs after
	# the camera's, so the snap is what stops it sliding in from the world origin.
	_camera.target = _player
	_camera.snap_to_target()

	_scatter_trees()


func _scatter_trees() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = scatter_seed

	var spawn := Vector2(_player.position.x, _player.position.z)
	var placed: Array[Vector2] = []
	var attempts := 0
	var max_attempts := tree_count * 40

	while placed.size() < tree_count and attempts < max_attempts:
		attempts += 1
		var spot := Vector2(
			rng.randf_range(-field_extent, field_extent),
			rng.randf_range(-field_extent, field_extent)
		)

		if absf(spot.x) < road_half_width:
			continue  # keep the road walkable
		if spot.distance_to(spawn) < spawn_clearance:
			continue
		if _is_crowded(spot, placed):
			continue

		var tree := TREE_SCENE.instantiate() as Node3D
		tree.position = Vector3(spot.x, 0.0, spot.y)
		tree.rotation.y = rng.randf_range(0.0, TAU)
		# Uniform only — a non-uniform scale on a cylinder shape upsets Jolt.
		tree.scale = Vector3.ONE * rng.randf_range(0.85, 1.2)
		_trees.add_child(tree)
		placed.append(spot)


func _is_crowded(spot: Vector2, placed: Array[Vector2]) -> bool:
	for other in placed:
		if spot.distance_to(other) < min_tree_spacing:
			return true
	return false
