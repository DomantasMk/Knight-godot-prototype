extends CanvasLayer

## Minimal demo readout: a chop counter and a controls hint.
##
## Counts felled trees straight off the EventBus, so it never holds a reference to
## a tree or to the level — which is the whole point of routing through the bus.

@onready var _chopped_label: Label = %ChoppedLabel

var _chopped_count: int = 0


func _ready() -> void:
	EventBus.tree_chopped.connect(_on_tree_chopped)
	_refresh()


func _on_tree_chopped(_tree: Node3D) -> void:
	_chopped_count += 1
	_refresh()


func _refresh() -> void:
	_chopped_label.text = "Trees chopped: %d" % _chopped_count
