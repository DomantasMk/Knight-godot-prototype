class_name HealthComponent
extends Node

## Tracks hit points for the entity this node is a child of.
##
## Knows nothing about where damage comes from — a HurtboxComponent (or any
## caller) routes it in through take_damage(). Everything else reacts to the
## signals, so the owning entity never has to poll.

signal health_changed(current: int, maximum: int)
signal died

@export var max_health: int = 3

var current_health: int


func _ready() -> void:
	current_health = max_health


func take_damage(amount: int) -> void:
	# Already dead: swallow the hit so `died` can never fire twice.
	if current_health <= 0:
		return
	current_health = maxi(current_health - amount, 0)
	health_changed.emit(current_health, max_health)
	if current_health == 0:
		died.emit()


func is_alive() -> bool:
	return current_health > 0
