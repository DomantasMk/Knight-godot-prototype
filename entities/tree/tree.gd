extends StaticBody3D

## A choppable greybox tree: blocks movement, flashes when struck, falls over when
## its HealthComponent runs out.
##
## Deliberately no class_name — "Tree" reads as SceneTree to anyone skimming, and
## nothing needs to type-check against this scene.

## Emission energy at the peak of the hit flash.
const FLASH_ENERGY: float = 1.6
const FLASH_DURATION: float = 0.25
const PUNCH_DURATION: float = 0.18
const FALL_DURATION: float = 0.55

@onready var _trunk_collision: CollisionShape3D = %TrunkCollision
@onready var _visuals: Node3D = %Visuals
@onready var _health: HealthComponent = %Health
@onready var _hurtbox: HurtboxComponent = %Hurtbox

var _materials: Array[StandardMaterial3D] = []
var _hit_tween: Tween


func _ready() -> void:
	# Wired here rather than through @export: node references exported into a
	# hand-written .tscn are not reliably resolved at load time.
	_hurtbox.health_component = _health
	# Feedback keys off the hit itself so it fires on the same frame; the broadcast
	# keys off health_changed, because `hurt` fires *before* damage is applied and
	# would report the pre-hit total as the remainder.
	_hurtbox.hurt.connect(_on_hurt)
	_health.health_changed.connect(_on_health_changed)
	_health.died.connect(_on_died)

	# Every tree instances the same imported mesh, and therefore the same materials.
	# Without a per-instance copy, hitting one tree lights up the whole forest.
	# Walked rather than named: the model is an imported glTF scene, so its mesh
	# nodes belong to the asset and are not ours to pin unique names on.
	for mesh_instance in _find_mesh_instances(_visuals):
		_materials.append_array(_make_flashable_materials(mesh_instance))


func _on_health_changed(current: int, _maximum: int) -> void:
	EventBus.tree_hit.emit(self, current)


func _on_hurt(_damage: int) -> void:
	if _hit_tween and _hit_tween.is_valid():
		_hit_tween.kill()
	_hit_tween = create_tween().set_parallel(true)

	# Snap to full brightness, then fade — a hit should read on the first frame.
	for material in _materials:
		material.emission_energy_multiplier = FLASH_ENERGY
		_hit_tween.tween_property(material, "emission_energy_multiplier", 0.0, FLASH_DURATION)

	# Squash only the visuals; the collision shapes must stay uniformly scaled,
	# or Jolt complains about non-uniform scale on a cylinder.
	_visuals.scale = Vector3(1.12, 0.88, 1.12)
	(_hit_tween.tween_property(_visuals, "scale", Vector3.ONE, PUNCH_DURATION)
		.set_trans(Tween.TRANS_BACK)
		.set_ease(Tween.EASE_OUT))


func _on_died() -> void:
	_hurtbox.monitorable = false
	# Deferred: never reshape a physics body from inside a physics callback.
	_trunk_collision.set_deferred("disabled", true)
	EventBus.tree_chopped.emit(self)

	if _hit_tween and _hit_tween.is_valid():
		_hit_tween.kill()

	# Euler order is YXZ, so a z-tilt lands in the tree's own frame — each tree
	# topples in the direction of its scattered yaw rather than all the same way.
	var fall := create_tween().set_parallel(true)
	fall.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	fall.tween_property(self, "rotation:z", PI / 2.0, FALL_DURATION)
	fall.tween_property(self, "position:y", position.y - 0.2, FALL_DURATION)
	fall.chain().tween_interval(0.2)
	await fall.finished
	queue_free()


func _find_mesh_instances(root: Node) -> Array[MeshInstance3D]:
	var found: Array[MeshInstance3D] = []
	for child in root.get_children():
		if child is MeshInstance3D:
			found.append(child)
		found.append_array(_find_mesh_instances(child))
	return found


## Gives [param mesh_instance] its own copy of each surface material, wired so the
## hit flash can drive emission.
##
## Per-surface overrides rather than a single [member GeometryInstance3D.material_override]:
## the imported tree is one mesh carrying a bark surface and a foliage surface, and
## one override would collapse both to a single colour.
func _make_flashable_materials(mesh_instance: MeshInstance3D) -> Array[StandardMaterial3D]:
	var made: Array[StandardMaterial3D] = []
	if mesh_instance.mesh == null:
		return made

	for surface in mesh_instance.mesh.get_surface_count():
		var source := mesh_instance.get_active_material(surface) as StandardMaterial3D
		var material: StandardMaterial3D = source.duplicate() if source else StandardMaterial3D.new()
		material.emission_enabled = true
		material.emission = Color.WHITE
		material.emission_energy_multiplier = 0.0
		mesh_instance.set_surface_override_material(surface, material)
		made.append(material)
	return made
