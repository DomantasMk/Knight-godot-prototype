"""Blender headless: turn a SkinTokens-predicted rig into one that can be animated.

    blender -b -P bl_normalize_rig.py -- <rigged.glb> <normalized.glb>

SkinTokens predicts a good skeleton and bad metadata. On the knight it produced 36 joints
in an exactly symmetric, anatomically correct humanoid hierarchy - and named them
`bone_0` ... `bone_35`, with rest orientations that mostly do not follow the limbs they
belong to (the thigh bone's tail pointed 60 degrees out to the side). Joint *positions* are
what the skin weights depend on, and those are right; everything this script fixes is
metadata that only matters once something tries to pose the rig.

Four things happen here, in this order, and the order matters:

1. **Name by hierarchy and position, never by name.** Predicted names carry no information,
   so the mapping walks the tree from the root and classifies each branch by where it sits
   in space - a child of the hips on the character's +X side is the left leg, whatever it
   is called. That is also what makes this reusable for the next character instead of being
   a lookup table for one rig. Every assumption is asserted, so a re-rolled skeleton with a
   different shape fails loudly here rather than producing a silently mislabelled rig.

2. **Turn the character to face Godot-forward.** Blender characters face -Y, which the glTF
   exporter writes as +Z - and a Node3D's forward in Godot is -Z, so an asset exported the
   normal way arrives facing backwards. `player.gd` computes yaw as `atan2(-x, -z)`, i.e. it
   assumes -Z, so the 180 degrees is baked into the asset here rather than hidden in a
   correction transform in the scene. Naming happens first, because after this rotation the
   character's left is no longer on +X.

3. **Rebuild tails and rolls.** Each bone's tail is moved onto its primary child's head, so
   a bone points along the limb it drives, and every roll is then set so the bone's local Z
   faces the character's front. That makes local X the flexion axis for the whole skeleton -
   knees, elbows, hips and spine all bend on the same local axis - which is the difference
   between authoring `bl_author_anims.py` and guessing at 30 bones' axes one at a time.
   Editing rest orientation does not deform the mesh: at rest the pose matrix equals the
   rest matrix, so their product is identity no matter what the tail does.

4. **Add the WeaponSocket empty, bone-parented to the right hand.** Godot's glTF importer
   turns a bone-parented node into a `BoneAttachment3D` by itself, which is what lets the
   sword hang off a hand bone from a hand-written `.tscn` without editable children.

The vertex-colour material is rebuilt rather than trusted: COLOR_0 is this project's only
albedo (see context/conventions.md) and several tools in the chain drop it quietly.
"""
import sys
import math

import bpy
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]

# Where the sword's own origin (the butt of its pommel) has to sit relative to the fist for
# the grip to land in the hand. sword_lowpoly.glb is 1.0 m with its blade along +Y, pommel
# at y=0 and crossguard at y=0.30, so the fist closes around y=0.18.
GRIP_INSET = 0.18

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

arm = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
mesh_obj = next((o for o in bpy.context.scene.objects if o.type == "MESH"), None)
if arm is None or mesh_obj is None:
    raise SystemExit("[rig] need one armature and one mesh in the input")
print(f"[rig] armature={arm.name} bones={len(arm.data.bones)} mesh={mesh_obj.name} "
      f"verts={len(mesh_obj.data.vertices)}")


# --- 1. name the skeleton by shape ---------------------------------------------
def head(bone):
    return arm.matrix_world @ bone.head_local


def children(bone):
    return list(bone.children)


def excluding(bones, exclude):
    """Filter by name, never by identity.

    Blender hands back a fresh Python wrapper on every RNA access, so two reads of the same
    `bone.children` produce objects that are `==` but not `is`. Filtering an identity out of
    a second read silently keeps it - which put the neck in the list of arms.
    """
    return [b for b in bones if b.name != exclude.name]


def chain_from(bone, names, renames):
    """Name a straight run of bones, following the single child at each step.

    Returns the bone that ended the run - the branch point below the last name, or None
    when the chain simply ran out.
    """
    start = bone.name
    named = []
    for name in names:
        if bone is None:
            raise SystemExit(f"[rig] chain from {start!r} ended after {named} but still "
                             f"expected {name!r}")
        renames[bone.name] = name
        named.append(f"{bone.name}->{name}")
        kids = children(bone)
        bone = kids[0] if len(kids) == 1 else None
    return bone


roots = [b for b in arm.data.bones if b.parent is None]
if len(roots) != 1:
    raise SystemExit(f"[rig] expected exactly one root bone, found {len(roots)}")
hips = roots[0]

renames = {hips.name: "Hips"}

hip_kids = children(hips)
if len(hip_kids) != 3:
    raise SystemExit(f"[rig] hips should branch into spine + two legs, got {len(hip_kids)}")

# The spine leaves the hips going up; the legs leave going down and to the sides.
spine_root = max(hip_kids, key=lambda b: head(b).z)
legs = excluding(hip_kids, spine_root)
if len(legs) != 2:
    raise SystemExit("[rig] could not separate the spine from the legs")

# The character faces -Y on import (Blender's convention, which glTF writes as +Z). Derive
# it from the feet rather than assuming: the toes are the most forward thing on the rig.
front = mathutils.Vector((0.0, -1.0, 0.0))
toe_y = min(head(b).y for b in arm.data.bones)
if toe_y > -0.02:
    raise SystemExit(f"[rig] no bone sits forward of the origin (min y={toe_y:+.3f}); "
                     "the character may not be facing -Y")
# With the character facing -Y and +Z up, its own left hand is on +X.
side_name = {1: "Left", -1: "Right"}

# Spine: walk up until the bone that carries both the neck and the shoulders.
spine_names = ["Spine", "Chest", "UpperChest"]
bone = spine_root
for depth, name in enumerate(spine_names):
    renames[bone.name] = name
    kids = children(bone)
    if len(kids) == 3:
        break
    if len(kids) != 1:
        raise SystemExit(f"[rig] spine bone {bone.name!r} has {len(kids)} children")
    bone = kids[0]
else:
    raise SystemExit("[rig] never reached the neck/shoulder branch walking the spine")

upper_chest = bone
chest_kids = children(upper_chest)
neck_root = min(chest_kids, key=lambda b: abs(head(b).x))
arms = excluding(chest_kids, neck_root)

chain_from(neck_root, ["Neck", "Head"], renames)

for arm_root in arms:
    side = side_name[1 if head(arm_root).x > 0 else -1]
    hand = chain_from(arm_root, [f"{side}Shoulder", f"{side}UpperArm",
                                 f"{side}LowerArm", f"{side}Hand"], renames)
    # chain_from stops at the branch, so re-fetch the hand it named.
    hand = next(b for b in arm.data.bones if renames.get(b.name) == f"{side}Hand")
    fingers = children(hand)
    if len(fingers) == 2:
        wrist_dir = (head(hand) - head(hand.parent)).normalized()
        # The finger that continues straight off the forearm is the index; the one that
        # peels away from that axis is the thumb.
        ranked = sorted(fingers, key=lambda b: (head(b) - head(hand)).normalized().dot(wrist_dir))
        chain_from(ranked[0], [f"{side}ThumbMetacarpal", f"{side}ThumbProximal",
                               f"{side}ThumbDistal"], renames)
        chain_from(ranked[1], [f"{side}IndexProximal", f"{side}IndexIntermediate",
                               f"{side}IndexDistal"], renames)
    else:
        for i, finger in enumerate(fingers):
            chain_from(finger, [f"{side}Finger{i}_{j}" for j in range(1, 5)], renames)

for leg_root in legs:
    side = side_name[1 if head(leg_root).x > 0 else -1]
    chain_from(leg_root, [f"{side}UpperLeg", f"{side}LowerLeg", f"{side}Foot",
                          f"{side}Toes", f"{side}ToesEnd"], renames)

unnamed = [b.name for b in arm.data.bones if b.name not in renames]
if unnamed:
    raise SystemExit(f"[rig] {len(unnamed)} bones were not classified: {unnamed}")

# Renaming a bone renames the matching vertex group, so weights follow the new names. Do it
# in two passes: predicted names like `bone_1` cannot collide with humanoid names, but a
# rerun on an already-normalized file would.
groups = {g.name for g in mesh_obj.vertex_groups}
for old, new in renames.items():
    arm.data.bones[old].name = new
print(f"[rig] renamed {len(renames)} bones")

missing = [n for n in renames.values() if n not in {g.name for g in mesh_obj.vertex_groups}]
if missing and groups:
    raise SystemExit(f"[rig] vertex groups did not follow the rename: {missing[:6]}")

for required in ("Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot"):
    if required not in arm.data.bones:
        raise SystemExit(f"[rig] {required} missing after naming")
print(f"[rig] right hand at {tuple(round(v, 3) for v in head(arm.data.bones['RightHand']))}, "
      f"head at {tuple(round(v, 3) for v in head(arm.data.bones['Head']))}")


# --- 2. turn the character to face Godot-forward -------------------------------
# Rotate the mesh data and the rest bones directly rather than setting an object rotation
# and calling transform_apply: that operator quietly does nothing on an armature with a
# parented mesh, and reports success either way, so the asset exports still facing
# backwards. Transforming both datablocks by the same matrix leaves the bind intact - at
# rest the pose matrix still equals the rest matrix.
TURN = mathutils.Matrix.Rotation(math.pi, 4, "Z")
mesh_obj.data.transform(TURN)
mesh_obj.data.update()

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for eb in arm.data.edit_bones:
    eb.transform(TURN)
bpy.ops.object.mode_set(mode="OBJECT")

front = mathutils.Vector((0.0, 1.0, 0.0))       # after the 180, the character faces +Y
toes = arm.data.bones["LeftToes"]
if (arm.matrix_world @ toes.head_local).y <= 0.0:
    raise SystemExit("[rig] the toes did not end up forward of the origin after the turn")
print("[rig] rotated 180 deg about Z; character now faces +Y in Blender (-Z in Godot)")


# --- 3. rebuild tails and rolls ------------------------------------------------
# A bone with several children follows the one that continues its limb; everything else
# hangs off it. Spelled out rather than inferred, because "primary" is a claim about
# anatomy that position alone cannot make for the hips.
PRIMARY_CHILD = {
    "Hips": "Spine",
    "UpperChest": "Neck",
    "LeftHand": "LeftIndexProximal",
    "RightHand": "RightIndexProximal",
}

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
edit_bones = arm.data.edit_bones

retargeted = 0
for eb in edit_bones:
    kids = list(eb.children)
    if not kids:
        continue
    if len(kids) > 1:
        wanted = PRIMARY_CHILD.get(eb.name)
        if wanted is None:
            raise SystemExit(f"[rig] {eb.name!r} has {len(kids)} children and no primary")
        target = edit_bones[wanted]
    else:
        target = kids[0]
    if (target.head - eb.head).length < 1e-5:
        continue
    eb.tail = target.head
    retargeted += 1

# Leaf bones have nothing to point at, so they continue their parent's direction over their
# own original length - which keeps fingertips and the head from collapsing to zero length.
for eb in edit_bones:
    if eb.children or eb.parent is None:
        continue
    direction = (eb.parent.tail - eb.parent.head).normalized()
    eb.tail = eb.head + direction * max(eb.length, 0.02)

# Local Z toward the character's front makes local X the flexion axis everywhere. A bone
# already pointing along the front (the toes) has no meaningful roll about that vector, so
# it falls back to world up.
for eb in edit_bones:
    axis = (eb.tail - eb.head).normalized()
    reference = front if abs(axis.dot(front)) < 0.94 else mathutils.Vector((0.0, 0.0, 1.0))
    eb.align_roll(reference)

bpy.ops.object.mode_set(mode="OBJECT")
print(f"[rig] retargeted {retargeted} tails, rolled {len(arm.data.bones)} bones to front")


# --- 4. the weapon socket ------------------------------------------------------
hand = arm.data.bones["RightHand"]
hand_head = arm.matrix_world @ hand.head_local
hand_tail = arm.matrix_world @ hand.tail_local
fist = hand_head.lerp(hand_tail, 0.5)

# The blade runs along the socket's +Y, so the sword's origin sits GRIP_INSET back down the
# blade from the fist. Blade up and the flat of the blade facing the character's side is
# the neutral carry; the attack clip rotates the arm, not this.
blade = mathutils.Vector((0.0, 0.0, 1.0))
socket_rot = mathutils.Matrix((
    (1.0, 0.0, 0.0),
    (0.0, 0.0, -1.0),
    (0.0, 1.0, 0.0),
)).to_4x4()                                       # local +Y -> world +Z

socket = bpy.data.objects.new("WeaponSocket", None)
socket.empty_display_type = "ARROWS"
socket.empty_display_size = 0.15
bpy.context.scene.collection.objects.link(socket)
socket.parent = arm
socket.parent_type = "BONE"
socket.parent_bone = "RightHand"
bpy.context.view_layer.update()

target = mathutils.Matrix.Translation(fist - blade * GRIP_INSET) @ socket_rot
socket.matrix_world = target
bpy.context.view_layer.update()
print(f"[rig] WeaponSocket on RightHand at "
      f"{tuple(round(v, 3) for v in socket.matrix_world.translation)} "
      f"(fist {tuple(round(v, 3) for v in fist)})")


# --- 5. guarantee the vertex-colour albedo -------------------------------------
mesh = mesh_obj.data
if not mesh.color_attributes:
    raise SystemExit("[rig] mesh has no colour attribute - COLOR_0 was lost upstream")
colour = mesh.color_attributes[0]
mesh.color_attributes.active_color = colour
mesh.color_attributes.render_color_index = 0
print(f"[rig] colour attribute {colour.name!r} domain={colour.domain} type={colour.data_type}")

mesh.materials.clear()
mat = bpy.data.materials.new("VertexColor")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.7
cnode = nt.nodes.new("ShaderNodeVertexColor")
cnode.layer_name = colour.name
nt.links.new(cnode.outputs["Color"], bsdf.inputs["Base Color"])
mesh.materials.append(mat)

name = bpy.path.display_name_from_filepath(dst)
mesh_obj.name = name
mesh.name = name + "Mesh"

bpy.ops.export_scene.gltf(
    filepath=dst,
    export_format="GLB",
    export_apply=False,        # never evaluate modifiers: that would flatten the armature
    export_yup=True,
    export_skins=True,
)
print(f"[rig] wrote {dst}")
