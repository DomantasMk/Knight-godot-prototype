@tool
extends "res://tools/import/vertex_color_material.gd"

## Import script for the rigged knight: the inherited vertex-colour fix, plus the two things
## the clips need that a GLB cannot carry - per-clip loop modes and the Call Method track
## that lands the sword hit.
##
## glTF has no event or marker track, so the impact frame cannot survive the export out of
## Blender - it has to be re-attached on the Godot side. Doing it here, at import time, keeps
## the clip reproducible and headless. The alternative is turning on "Save to File" for the
## `attack` clip and hand-editing the generated `.res`, which has to be redone by hand every
## time the animation is re-authored - and re-authoring happens in a different repo entirely
## (see CLAUDE.md), so it must not depend on anything remembered here.
##
## Loop modes belong in the `.import` file's `_subresources` block by rights, and were there
## first. The problem is that one entry there makes Godot write out slice_1..slice_100 of
## defaults per clip on every reimport - 279 KB of generated noise in a 1.2 KB file, dirty
## again after any clone-and-import. Setting loop_mode here costs a dictionary and keeps the
## whole clip contract in one readable place.
##
## Wire it up in assets/models/knight_rigged_v2.glb.import, replacing the plain vertex-colour
## script (this one calls it):
##     import_script/path="res://tools/import/knight_rigged_import.gd"
##
## Editing *this* file does not trigger a reimport - Godot keys those off the source asset, so
## the constant below changes and nothing happens until the cached
## .godot/imported/knight_rigged_v2.glb-*.scn is deleted and --headless --import re-run. Never
## delete the .glb.import instead; that mints a new UID and orphans every ext_resource.

## Looping locomotion, one-shot actions. glTF carries no loop mode, so this table restates what
## the pipeline handed over. Asserted by tools/verify/verify_rigged_import.gd.
const LOOP_MODES := {
	&"idle": Animation.LOOP_LINEAR,
	&"run": Animation.LOOP_LINEAR,
	&"attack": Animation.LOOP_NONE,
	&"roll": Animation.LOOP_NONE,
	&"jump": Animation.LOOP_NONE,
}

## Frame 8 of 18 at 30 fps, where the ATTACK clip poses contact - and, for the first time, also
## where the blade is actually fastest. Measured with the asset pipeline's
## blade_speed.py: the tip peaks at 29.9 m/s entering frame 8, which is 100% of
## the clip's peak, and sits 0.70 m from the Hitbox sphere's centre (radius 1.1).
##
## That agreement is authored, not lucky. The previous 15-frame clip peaked at 37.2 m/s two
## frames *before* its contact pose and had decayed to 15.5 m/s by the time it got there,
## because the exporter force-samples at 30 fps and bakes Blender's default auto-Bezier
## ease-in into every key; this constant had to be pulled back to 7/30 to compensate. The
## rewrite eases into contact on purpose (SINE/EASE_IN out of the held coil), so the peak and
## the pose are the same frame and no compensation is needed.
##
## Do not move this by eye. Re-measure first - the peak frame is a property of the easing, not
## of the poses, and nothing about the clip's shape advertises where it is.
const ATTACK_IMPACT_TIME := 8.0 / 30.0

## Method-track paths resolve against the AnimationMixer's `root_node`, and the mixer here is
## the player's AnimationTree, whose `root_node` points at this instanced model. Two levels up
## from the model is the Player: Model -> Visuals -> Player. Coupled to the shape of
## entities/player/player.tscn on purpose; tools/verify/verify_player_scene.gd asserts it
## still resolves, and fails the build if either side moves.
const PLAYER_PATH := NodePath("../..")

const IMPACT_METHOD := &"deal_attack_damage"


func _post_import(scene: Node) -> Object:
	super(scene)
	var player := _find_animation_player(scene)
	if player == null:
		push_error("knight_rigged_import: no AnimationPlayer, the clips cannot be wired")
		return scene
	_set_loop_modes(player)
	_add_attack_impact(player)
	return scene


func _set_loop_modes(player: AnimationPlayer) -> void:
	for clip: StringName in LOOP_MODES:
		if not player.has_animation(clip):
			push_error("knight_rigged_import: no '%s' clip (have: %s)" %
					[clip, ", ".join(player.get_animation_list())])
			continue
		player.get_animation(clip).loop_mode = LOOP_MODES[clip]


func _add_attack_impact(player: AnimationPlayer) -> void:
	if not player.has_animation(&"attack"):
		return

	var attack := player.get_animation(&"attack")
	var track := attack.add_track(Animation.TYPE_METHOD)
	attack.track_set_path(track, PLAYER_PATH)
	attack.track_insert_key(track, ATTACK_IMPACT_TIME, {
		"method": IMPACT_METHOD,
		"args": [],
	})
	print("knight_rigged_import: %s() on 'attack' at %.3fs (track %d, path %s)" %
			[IMPACT_METHOD, ATTACK_IMPACT_TIME, track, PLAYER_PATH])


func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for child in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null
