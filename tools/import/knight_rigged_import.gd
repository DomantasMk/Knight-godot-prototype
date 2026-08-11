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
## time the animation is re-authored in `tools/rigging/bl_author_anims.py`.
##
## Loop modes belong in the `.import` file's `_subresources` block by rights, and were there
## first. The problem is that one entry there makes Godot write out slice_1..slice_100 of
## defaults per clip on every reimport - 279 KB of generated noise in a 1.2 KB file, dirty
## again after any clone-and-import. Setting loop_mode here costs a dictionary and keeps the
## whole clip contract in one readable place.
##
## Wire it up in assets/models/knight_rigged.glb.import, replacing the plain vertex-colour
## script (this one calls it):
##     import_script/path="res://tools/import/knight_rigged_import.gd"

## Looping locomotion, one-shot actions. Asserted by tools/rigging/verify_rigged_import.gd.
const LOOP_MODES := {
	&"idle": Animation.LOOP_LINEAR,
	&"run": Animation.LOOP_LINEAR,
	&"attack": Animation.LOOP_NONE,
	&"roll": Animation.LOOP_NONE,
	&"jump": Animation.LOOP_NONE,
}

## Frame 8 of 15 at 30 fps, straight out of bl_author_anims.py's ATTACK block: the pose where
## the blade is out in front and its tip sits inside the player's Hitbox sphere. Syncing to
## the art beats the timer this replaces, which guessed 0.12s and landed the hit early.
const ATTACK_IMPACT_TIME := 8.0 / 30.0

## Method-track paths resolve against the AnimationMixer's `root_node`, and the mixer here is
## the player's AnimationTree, whose `root_node` points at this instanced model. Two levels up
## from the model is the Player: Model -> Visuals -> Player. Coupled to the shape of
## entities/player/player.tscn on purpose; tools/rigging/verify_player_scene.gd asserts it
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
