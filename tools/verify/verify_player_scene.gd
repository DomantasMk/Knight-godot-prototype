@tool
extends SceneTree

## Assert that the player scene is wired to the rigged knight and that the swing lands.
##
##     & $godot --path . --headless --script res://tools/verify/verify_player_scene.gd
##
## verify_rigged_import.gd covers the asset. This covers the seam between the asset and the
## game, which is where the wiring can fail quietly:
##
## - The sword hangs off the generated BoneAttachment3D, not off a pivot bolted to the body.
## - The AnimationTree is `active`, points at the model's AnimationPlayer, and resolves its
##   `root_node` to the model - an AnimationTree whose root_node is wrong finds none of its
##   108 bone tracks and the knight simply stands in its T-pose rest.
## - Every state pair player.gd travels between has a transition. A missing one is not an
##   error: travel() silently hard-cuts instead of blending, which reads as a pop.
## - **The swing actually deals damage.** The Call Method track resolves its target through
##   the AnimationTree's root_node, so its path (`../..`) encodes the shape of this scene.
##   Move the model one level and the swing still plays, still looks right, and hits nothing.
##   This is the one that would cost a session, so it is not inspected but *run*: the tree is
##   advanced by hand through the attack clip and the strike is observed.

const SCENE := "res://entities/player/player.tscn"
const SOCKET_PATH := "Visuals/Model/Armature/Skeleton3D/RightHand/WeaponSocket"
const STATES := ["idle", "run", "attack", "roll", "jump"]
## Every transition player.gd's _advance_state() can ask for, plus the entry edge.
const TRANSITIONS := [
	["Start", "idle"],
	["idle", "run"], ["run", "idle"],
	["idle", "attack"], ["run", "attack"],
	["idle", "roll"], ["run", "roll"],
	["idle", "jump"], ["run", "jump"],
	["attack", "idle"], ["attack", "run"],
	["roll", "idle"], ["roll", "run"],
	["jump", "idle"], ["jump", "run"],
]

var _failures: PackedStringArray = []


## Everything happens on the first frame, not in _initialize(): the scene has to be *in* the
## tree for _ready() to run, and the root window is not ready to take children that early.
func _process(_delta: float) -> bool:
	var packed := load(SCENE) as PackedScene
	if packed == null:
		_fail("could not load %s" % SCENE)
		return _finish()

	var player := packed.instantiate()
	print("[verify] root %s (%s)" % [player.name, player.get_class()])

	_check_sword(player)
	var tree := _check_tree(player)
	if tree != null:
		_check_states(tree)
		_run_attack(player, tree)

	player.free()
	return _finish()


func _fail(message: String) -> void:
	_failures.append(message)


func _check_sword(player: Node) -> void:
	if player.get_node_or_null("WeaponPivot") != null:
		_fail("WeaponPivot is still here - the sword is bolted to the body, not to the hand")
	var socket := player.get_node_or_null(SOCKET_PATH)
	if socket == null:
		_fail("no %s - the bone-parented empty did not survive import" % SOCKET_PATH)
		return
	var sword := socket.get_node_or_null("Sword") as Node3D
	if sword == null:
		_fail("no Sword under %s" % SOCKET_PATH)
		return
	if not sword.transform.is_equal_approx(Transform3D.IDENTITY):
		_fail("Sword carries its own transform - the socket is supposed to be the whole grip")
	print("[verify] Sword under %s" % SOCKET_PATH)


func _check_tree(player: Node) -> AnimationTree:
	var tree := player.get_node_or_null("%AnimationTree") as AnimationTree
	if tree == null:
		_fail("no %AnimationTree - player.gd's _ready() will crash on it")
		return null
	if not tree.active:
		_fail("AnimationTree is not active - nothing will animate")

	# root_node is what every track path resolves against, the 108 bone tracks included.
	var root := tree.get_node_or_null(tree.root_node)
	if root == null:
		_fail("AnimationTree.root_node (%s) resolves to nothing" % tree.root_node)
	elif root.get_node_or_null("Armature/Skeleton3D") == null:
		_fail("AnimationTree.root_node (%s) is not the model - bone tracks will not resolve"
				% tree.root_node)

	var anim_player := tree.get_node_or_null(tree.anim_player) as AnimationPlayer
	if anim_player == null:
		_fail("AnimationTree.anim_player (%s) resolves to no AnimationPlayer" % tree.anim_player)
		return null
	print("[verify] AnimationTree active=%s root_node=%s anim_player=%s" %
			[tree.active, tree.root_node, tree.anim_player])
	return tree


func _check_states(tree: AnimationTree) -> void:
	var machine := tree.tree_root as AnimationNodeStateMachine
	if machine == null:
		_fail("tree_root is %s, not an AnimationNodeStateMachine" % tree.tree_root)
		return
	for state in STATES:
		if not machine.has_node(state):
			_fail("no state named %s - player.gd travels to it by name" % state)
	for edge in TRANSITIONS:
		if not machine.has_transition(edge[0], edge[1]):
			_fail("no transition %s -> %s - travel() will hard-cut instead of blending" % edge)
	print("[verify] state machine: %d transitions covering %d wanted" %
			[machine.get_transition_count(), TRANSITIONS.size()])


## The real gate. Drive the clip and watch for the hit rather than reading the track's path
## and hoping: a path that resolves to the wrong node reads perfectly well.
func _run_attack(player: Node, tree: AnimationTree) -> void:
	get_root().add_child(player)

	# Manual + immediate so the clip advances in known steps and the call is not deferred to
	# an idle frame that a headless one-shot run never gets around to.
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	tree.callback_mode_method = AnimationMixer.ANIMATION_CALLBACK_MODE_METHOD_IMMEDIATE

	var playback := tree.get("parameters/playback") as AnimationNodeStateMachinePlayback
	if playback == null:
		_fail("no parameters/playback on the AnimationTree")
		get_root().remove_child(player)
		return

	for i in 8:
		tree.advance(0.05)
	if playback.get_current_node() != &"idle":
		_fail("settled into %s, expected idle" % playback.get_current_node())

	playback.travel(&"attack")
	var elapsed := 0.0
	while elapsed < 0.6 and not player.get("_struck"):
		tree.advance(0.02)
		elapsed += 0.02

	if player.get("_struck"):
		print("[verify] deal_attack_damage() fired after %.2fs of advancing the tree" % elapsed)
	else:
		_fail("the attack clip ran to the end and deal_attack_damage() never fired - the " +
				"Call Method track's path does not reach the Player from the model")

	_report_grip(player)
	get_root().remove_child(player)


## Not asserted, just reported: a number to eyeball if the grip ever looks wrong. Read off the
## skeleton rather than off the Sword node - a BoneAttachment3D only catches up on a real
## frame, and this run advances the tree by hand, so the node is still sitting at rest.
func _report_grip(player: Node) -> void:
	var skeleton := player.get_node_or_null("Visuals/Model/Armature/Skeleton3D") as Skeleton3D
	if skeleton == null:
		return
	var bone := skeleton.find_bone("RightHand")
	if bone == -1:
		return
	print("[verify] RightHand posed at %v (rest %v)" %
			[skeleton.get_bone_global_pose(bone).origin, skeleton.get_bone_global_rest(bone).origin])


func _finish() -> bool:
	if _failures.is_empty():
		print("[verify] OK")
		quit(0)
		return true
	for failure in _failures:
		printerr("[verify] FAIL: %s" % failure)
	quit(1)
	return true
