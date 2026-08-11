@tool
extends SceneTree

## Assert that an imported rigged model survived Godot's import step intact.
##
##     & $godot --path . --headless --script res://tools/rigging/verify_rigged_import.gd
##
## The Stage 5 gate is "the knight imports coloured, not white", and a headless run that
## exits 0 proves nothing about that - a white, unskinned, unanimated model loads perfectly
## well. Rendering a frame and looking at it costs ~250 tokens that then ride along for the
## whole session (see the screenshot rule in CLAUDE.md), so the cheap checks are asserted
## here instead and the picture is kept for the questions a number cannot answer.
##
## What it checks, and why each one has bitten this project or was one step from doing so:
##
## - `vertex_color_use_as_albedo` on every surface. Godot's glTF importer reads COLOR_0 but
##   never sets this flag, so without `tools/import/vertex_color_material.gd` the knight
##   imports pure white. This is the actual Stage 5 gate.
## - A Skeleton3D with the humanoid bone names, so the AnimationTree's tracks resolve.
## - The four clips, their durations, and their loop modes. Both the loop modes and the
##   attack clip's Call Method track are applied by `tools/import/knight_rigged_import.gd`,
##   which the `.import` file has to point at - an unwired import script fails silently.
## - The impact track itself. glTF cannot carry an event track, so if this one goes missing
##   the swing plays perfectly and deals no damage at all.
## - The BoneAttachment3D that Godot generates from the bone-parented `WeaponSocket` empty.
##   Without it there is nothing to hang the sword from.
##
## The other half of the gate - that the track's path still resolves to the player and that
## the hit actually lands - is `verify_player_scene.gd`, because it is a scene fact.

const MODEL := "res://assets/models/knight_rigged.glb"
const EXPECTED_CLIPS := {
	"idle": Animation.LOOP_LINEAR,
	"run": Animation.LOOP_LINEAR,
	"attack": Animation.LOOP_NONE,
	"roll": Animation.LOOP_NONE,
	"jump": Animation.LOOP_NONE,
}
const IMPACT_METHOD := &"deal_attack_damage"
const IMPACT_TIME := 8.0 / 30.0

var _failures: PackedStringArray = []


func _init() -> void:
	var scene := load(MODEL) as PackedScene
	if scene == null:
		_fail("could not load %s" % MODEL)
		_finish()
		return

	var root := scene.instantiate()
	print("[verify] root %s (%s)" % [root.name, root.get_class()])

	_check_colour(root)
	_check_skeleton(root)
	_check_animations(root)
	_check_socket(root)

	root.free()
	_finish()


func _fail(message: String) -> void:
	_failures.append(message)


## Every surface, not `material_override`: an imported mesh is an ArrayMesh, and an override
## collapses all of its surfaces onto one material. See context/conventions.md.
func _check_colour(root: Node) -> void:
	var meshes := 0
	for node in _walk(root):
		var mesh_instance := node as MeshInstance3D
		if mesh_instance == null or mesh_instance.mesh == null:
			continue
		meshes += 1
		for surface in mesh_instance.mesh.get_surface_count():
			var material := mesh_instance.mesh.surface_get_material(surface) as StandardMaterial3D
			if material == null:
				_fail("%s surface %d has no StandardMaterial3D" % [mesh_instance.name, surface])
			elif not material.vertex_color_use_as_albedo:
				_fail("%s surface %d ignores COLOR_0 - it will render white" %
						[mesh_instance.name, surface])
	if meshes == 0:
		_fail("no MeshInstance3D in the imported scene")
	print("[verify] %d mesh instance(s), vertex colour albedo checked" % meshes)


func _check_skeleton(root: Node) -> void:
	var skeleton: Skeleton3D = null
	for node in _walk(root):
		if node is Skeleton3D:
			skeleton = node
			break
	if skeleton == null:
		_fail("no Skeleton3D - the mesh cannot deform")
		return
	print("[verify] skeleton %s, %d bones" % [skeleton.name, skeleton.get_bone_count()])
	for bone in ["Hips", "Spine", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot"]:
		if skeleton.find_bone(bone) == -1:
			_fail("bone %s missing - the rig is not humanoid-named" % bone)


func _check_animations(root: Node) -> void:
	var player: AnimationPlayer = null
	for node in _walk(root):
		if node is AnimationPlayer:
			player = node
			break
	if player == null:
		_fail("no AnimationPlayer - the clips did not import")
		return

	for clip in EXPECTED_CLIPS:
		if not player.has_animation(clip):
			_fail("clip %s missing (have: %s)" % [clip, ", ".join(player.get_animation_list())])
			continue
		var animation := player.get_animation(clip)
		var wanted: int = EXPECTED_CLIPS[clip]
		if animation.loop_mode != wanted:
			_fail("clip %s has loop_mode %d, expected %d - check _subresources in the .import"
					% [clip, animation.loop_mode, wanted])
		print("[verify] clip %-7s %.2fs  %d tracks  loop=%d" %
				[clip, animation.length, animation.get_track_count(), animation.loop_mode])

	if player.has_animation("attack"):
		_check_impact_track(player.get_animation("attack"))


## The swing without this track is a swing that deals no damage - it plays, it looks right,
## and nothing takes a hit. Cheap to assert, expensive to notice by eye.
func _check_impact_track(attack: Animation) -> void:
	for track in attack.get_track_count():
		if attack.track_get_type(track) != Animation.TYPE_METHOD:
			continue
		for key in attack.track_get_key_count(track):
			var time := attack.track_get_key_time(track, key)
			var call: Dictionary = attack.track_get_key_value(track, key)
			if call.get("method", &"") != IMPACT_METHOD:
				continue
			if absf(time - IMPACT_TIME) > 0.01:
				_fail("%s() fires at %.3fs, expected %.3fs" % [IMPACT_METHOD, time, IMPACT_TIME])
			print("[verify] %s() at %.3fs on track %d, path %s" %
					[IMPACT_METHOD, time, track, attack.track_get_path(track)])
			return
	_fail(("attack has no Call Method track calling %s() - check import_script/path in the " +
			".import file, the swing will deal zero damage") % IMPACT_METHOD)


func _check_socket(root: Node) -> void:
	for node in _walk(root):
		var attachment := node as BoneAttachment3D
		if attachment != null:
			print("[verify] %s -> bone %s" % [attachment.name, attachment.bone_name])
			return
	_fail("no BoneAttachment3D - the WeaponSocket empty did not survive import")


func _walk(node: Node) -> Array[Node]:
	var out: Array[Node] = [node]
	for child in node.get_children():
		out.append_array(_walk(child))
	return out


func _finish() -> void:
	if _failures.is_empty():
		print("[verify] OK")
		quit(0)
		return
	for failure in _failures:
		printerr("[verify] FAIL: %s" % failure)
	quit(1)
