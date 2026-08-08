extends Node

## Owns high-level game flow: which level is loaded, and whether we are paused.
##
## Keep this small. When a rule grows past a few lines, move it into a plain
## class under systems/ and call it from here.

signal scene_changed(scene_path: String)
signal game_paused(is_paused: bool)

var current_level: String = ""
var is_paused: bool = false


func _ready() -> void:
	# Must keep processing while the tree is paused, or nothing can unpause us.
	process_mode = Node.PROCESS_MODE_ALWAYS


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause"):
		toggle_pause()
		get_viewport().set_input_as_handled()


func change_scene(path: String) -> void:
	current_level = path
	scene_changed.emit(path)
	get_tree().change_scene_to_file(path)


func set_paused(paused: bool) -> void:
	is_paused = paused
	get_tree().paused = paused
	game_paused.emit(paused)


func toggle_pause() -> void:
	set_paused(not is_paused)


func quit_game() -> void:
	get_tree().quit()
