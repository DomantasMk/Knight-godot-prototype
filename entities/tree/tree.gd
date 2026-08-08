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

	# Every tree instances the same meshes, and therefore the same materials.
	# Without a per-instance copy, hitting one tree lights up the whole forest.
	var mesh_instances: Array[MeshInstance3D] = [%Trunk, %Canopy]
	for mesh_instance in mesh_instances:
		_materials.append(_make_flashable_material(mesh_instance))


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


func _make_flashable_material(mesh_instance: MeshInstance3D) -> StandardMaterial3D:
	var source: StandardMaterial3D = null
	if mesh_instance.mesh is PrimitiveMesh:
		source = (mesh_instance.mesh as PrimitiveMesh).material as StandardMaterial3D

	var material: StandardMaterial3D = source.duplicate() if source else StandardMaterial3D.new()
	material.emission_enabled = true
	material.emission = Color.WHITE
	material.emission_energy_multiplier = 0.0
	mesh_instance.material_override = material
	return material
