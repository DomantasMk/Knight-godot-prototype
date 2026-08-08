class_name HurtboxComponent
extends Area3D

## The damageable volume of an entity. Forwards incoming hits to a HealthComponent.
##
## Sits on a detectable physics layer with an empty collision mask — it never
## detects anything itself, it only exists to be found by a HitboxComponent.

signal hurt(damage_amount: int)

## The HealthComponent this hurtbox feeds. Wire it from the owning entity's
## _ready(); @export node references are unreliable in hand-written .tscn files.
@export var health_component: HealthComponent


func receive_hit(damage: int) -> void:
	# A corpse absorbs nothing. Without this, a swing landing between death and
	# the death animation finishing would re-fire `hurt` and replay the feedback.
	if health_component and not health_component.is_alive():
		return
	hurt.emit(damage)
	if health_component:
		health_component.take_damage(damage)
