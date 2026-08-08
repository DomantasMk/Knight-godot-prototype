class_name HitboxComponent
extends Area3D

## The damaging volume of an attack. Only deals damage when strike() is called.
##
## Deliberately not automatic on area_entered: this is a swing-triggered melee
## hitbox, so standing next to a target must not damage it. Overlaps are tracked
## continuously instead, which means strike() lands on the frame it is called
## rather than waiting a physics tick for `monitoring` to warm up.

signal hit(target_hurtbox: HurtboxComponent)

@export var damage: int = 1

var _overlapping: Array[HurtboxComponent] = []


func _ready() -> void:
	area_entered.connect(_on_area_entered)
	area_exited.connect(_on_area_exited)


## Damages every hurtbox currently inside the volume. Returns how many were hit.
func strike() -> int:
	var count := 0
	# Iterate a copy: a lethal hit can free its target, mutating the live array.
	for hurtbox in _overlapping.duplicate():
		if not is_instance_valid(hurtbox):
			_overlapping.erase(hurtbox)
			continue
		hit.emit(hurtbox)
		hurtbox.receive_hit(damage)
		count += 1
	return count


func _on_area_entered(area: Area3D) -> void:
	var hurtbox := area as HurtboxComponent
	if hurtbox and not _overlapping.has(hurtbox):
		_overlapping.append(hurtbox)


func _on_area_exited(area: Area3D) -> void:
	var hurtbox := area as HurtboxComponent
	if hurtbox:
		_overlapping.erase(hurtbox)
