extends Node

## Headed playtest harness: boots a scene, drives it with scripted Input Map actions,
## and writes screenshots to disk so a change can be verified without a human watching.
##
## Rendering is why this runs in a real window -- `--headless` uses the dummy driver and
## every capture would come back blank. The window is shown briefly and closed on quit.
##
##     & $env:GODOT_BIN_CONSOLE --path . res://tools/playtest/playtest.tscn -- \
##         --scene=res://levels/level_01/level_01.tscn \
##         --out=res://local/playtest \
##         --scale=0.5 \
##         --steps="wait 0.5; shot start; hold move_forward 1.0; shot walked; tap attack; wait 0.5; shot swing"
##
## Captures are downscaled by `--scale` (default 0.5) before saving. This is a token
## budget, not a quality choice: an agent reading a PNG pays roughly width*height/750
## tokens for it, so halving each side is a 4x saving. Half size still resolves the HUD
## counter and body positions; pass --scale=1 when the question is genuinely fine detail.
##
## Prefer `expect` over `shot` wherever the question has a factual answer -- a failed
## assertion costs a line of stdout against ~250 tokens for an image, and it fails the run
## instead of relying on someone noticing. Screenshots stay the right tool when the
## question is genuinely visual: does the swing arc read, is the camera framed sensibly,
## did the material break. Those have no property to assert on.
##
## Exits non-zero if any `expect` failed, so this works as a smoke test in a pipeline.
##
## Steps (semicolon-separated, applied in order):
##   wait <seconds>              let the game run
##   tap <action>                press and release an action over one frame
##   hold <action> <seconds>     press, wait, release
##   press <action>              press and leave held
##   release <action>            release a held action
##   expect <expression>         assert the expression is true, else fail the run
##   show <expression>           print the expression's value (no pass/fail)
##   shot <name>                 capture <out>/<NN>_<name>.png
##
## `expect` and `show` evaluate against the booted scene's root, so its own methods,
## properties and unique names are in scope:
##
##     expect get_node("%Trees").get_child_count() == 26
##     expect get_node("%Player").position.y > 0.0
##     show get_node("%Player").position

const DEFAULT_SCENE := "res://levels/level_01/level_01.tscn"
const DEFAULT_OUT := "res://local/playtest"
const DEFAULT_STEPS := "wait 0.5; shot spawn; hold move_forward 1.2; shot walked; tap attack; wait 0.4; shot swing"

const DEFAULT_SCALE := 0.5

var _out_dir: String = DEFAULT_OUT
var _scale: float = DEFAULT_SCALE
var _shot_index: int = 0
var _held: Array[String] = []
var _scene: Node
var _passed: int = 0
var _failed: int = 0


func _ready() -> void:
	var args := _parse_args()
	_out_dir = args.get("out", DEFAULT_OUT)
	_scale = clampf(float(args.get("scale", DEFAULT_SCALE)), 0.1, 1.0)
	var scene_path: String = args.get("scene", DEFAULT_SCENE)
	var steps: String = args.get("steps", DEFAULT_STEPS)

	if not ResourceLoader.exists(scene_path):
		push_error("playtest: no such scene: %s" % scene_path)
		get_tree().quit(1)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out_dir))

	_scene = (load(scene_path) as PackedScene).instantiate()
	add_child(_scene)
	# One frame so the booted scene's _ready() work (camera snap, tree scatter) lands
	# before the first step runs.
	await get_tree().process_frame

	for step in steps.split(";", false):
		await _run_step(step.strip_edges())

	for action in _held.duplicate():
		_release(action)

	if _passed + _failed > 0:
		print("playtest: %d passed, %d failed" % [_passed, _failed])
	print("playtest: %d screenshot(s) in %s" % [_shot_index, _out_dir])
	get_tree().quit(1 if _failed > 0 else 0)


func _run_step(step: String) -> void:
	if step.is_empty():
		return
	var parts := step.split(" ", false)
	var verb := parts[0]

	match verb:
		"wait":
			await _wait(float(parts[1]))
		"expect":
			# Expressions contain spaces, so take the rest of the step verbatim.
			_expect(step.substr(verb.length()).strip_edges())
		"show":
			_show(step.substr(verb.length()).strip_edges())
		"shot":
			await _shot(parts[1] if parts.size() > 1 else "shot")
		"press":
			_press(parts[1])
		"release":
			_release(parts[1])
		"tap":
			_press(parts[1])
			# Two frames: one for _physics_process to see just_pressed, one to settle.
			await get_tree().physics_frame
			await get_tree().physics_frame
			_release(parts[1])
		"hold":
			_press(parts[1])
			await _wait(float(parts[2]))
			_release(parts[1])
		_:
			push_error("playtest: unknown step: %s" % step)


## Evaluates against the booted scene root, so `get_node("%Player").position` and the
## scene script's own members resolve without qualification.
func _evaluate(source: String) -> Variant:
	var expression := Expression.new()
	if expression.parse(source) != OK:
		_failed += 1
		printerr("playtest: FAIL parse [%s] -- %s" % [source, expression.get_error_text()])
		return null

	var result: Variant = expression.execute([], _scene, true)
	if expression.has_execute_failed():
		_failed += 1
		printerr("playtest: FAIL eval [%s] -- %s" % [source, expression.get_error_text()])
		return null
	return result


func _expect(source: String) -> void:
	var before := _failed
	var result: Variant = _evaluate(source)
	if _failed > before:
		return  # already counted and reported by _evaluate
	if result:
		_passed += 1
		print("playtest: PASS %s" % source)
	else:
		_failed += 1
		printerr("playtest: FAIL %s -- got %s" % [source, result])


func _show(source: String) -> void:
	var before := _failed
	var result: Variant = _evaluate(source)
	if _failed == before:
		print("playtest: %s = %s" % [source, result])


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func _press(action: String) -> void:
	if not InputMap.has_action(action):
		push_error("playtest: no such input action: %s" % action)
		return
	Input.action_press(action)
	if action not in _held:
		_held.append(action)


func _release(action: String) -> void:
	if InputMap.has_action(action):
		Input.action_release(action)
	_held.erase(action)


func _shot(name: String) -> void:
	# The viewport texture only holds this frame's result after the draw completes.
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	if _scale < 1.0:
		image.resize(
			maxi(int(image.get_width() * _scale), 1),
			maxi(int(image.get_height() * _scale), 1),
			Image.INTERPOLATE_BILINEAR
		)
	var path := "%s/%02d_%s.png" % [_out_dir, _shot_index, name]
	if image.save_png(path) != OK:
		push_error("playtest: could not write %s" % path)
		return
	_shot_index += 1
	print("playtest: wrote %s" % path)


## Reads `--key=value` pairs from the arguments after the `--` separator.
func _parse_args() -> Dictionary:
	var out := {}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--") and "=" in arg:
			var pair := arg.substr(2).split("=", true, 1)
			out[pair[0]] = pair[1]
	return out
