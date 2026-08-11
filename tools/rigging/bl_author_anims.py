"""Blender headless: author the player's animation clips on the normalized rig.

    blender -b -P bl_author_anims.py -- <normalized.glb> <animated.glb>

Input is `knight_normalized.glb` from `bl_normalize_rig.py`, not the raw SkinTokens
output. Every clip is authored here as scripted keyframes - there is no mocap library and
no retarget step, because the motion is written directly onto the rig that will play it.

Four clips, one Action each, stashed on NLA tracks so both the glTF exporter (Animation
Mode = Actions) and `bl_anim_contact_sheet.py` can find them:

    idle    2.0s  loop    breathing, weight shift, the sword arm drifting
    run     0.6s  loop    contact / down / airborne, twice, sides exchanged
    attack  0.5s  once    wind-up over the right shoulder, diagonal slash, follow-through
    roll    0.7s  once    tuck, a full forward revolution, recover

**All clips are in-place.** Translation stays driven by the velocity code in `player.gd`;
the only translation authored here is the vertical bob of the Hips, which is animation, not
travel.

## Why poses are written as world axes

`bl_normalize_rig.py` guarantees one invariant: every bone's local Z faces the character's
front. Local Y runs along the bone, so local X - the flexion axis - falls out of the bone's
own direction and therefore points a *different world direction on every bone*: world -X on
the spine, +X on the legs, and roughly vertical on the arms. Writing poses as raw local
angles needs a fresh sign convention per bone and is how a day gets lost.

So a pose here is a list of rotations about **world** axes, and `Pose.rotate` converts each
one into the bone's local frame. World axes have one meaning each, for every bone:

    +X  sagittal    forward/back swing. Rotating a joint about +X moves everything
                    *below* it forward and everything *above* it backward - so a thigh
                    swings forward on +X, a spine leans forward on -X, a knee flexes on -X.
    +Y  frontal     raise/lower and side bend. +Y raises the left arm and lowers the right.
    +Z  transverse  twist - pelvis and shoulder counter-rotation, toe-in/toe-out.

This goes one step further than the helper sketched in the handoff, which read the axis off
the bone's *rest* matrix. That is only a world axis while the bone's parents are unposed:
once the shoulder is rotated 70 degrees to bring the arm down out of its T-pose, the
forearm's rest X is no longer world X, and "bend the elbow forward" stops meaning that.
`Pose` therefore carries the accumulated pose down the chain, so an axis named here is the
true world axis no matter what the parents are doing. Two extra axis names cover what world
axes cannot say:

    twist   about the bone's own current direction - a wrist roll, an axial arm roll
    bend    about the bone's own current local X - the normalizer's flexion axis

The rest pose is a **T-pose**, so every clip starts from STANCE, which brings the arms down
and puts the sword up in a ready guard. Clip poses are deltas layered on top of it: their
ops are appended, and since each op is about a world axis they compose in the order listed.

## Mirroring

Left/right pairs take the *same* sign about world X and *opposite* signs about Y and Z,
because the mirror plane is the character's own sagittal plane. `swap_sides()` applies that
to the run cycle, whose second half really is its first half with the sides exchanged.
Nothing else is mirrored: the stance is deliberately asymmetric, since the sword is in the
right hand.

## Reading the report

The script prints, for every keyframe it writes, the world position of the head, hands and
feet and the direction the sword blade points. That is the cheap half of reviewing an
animation - it catches a foot through the floor or a sword swinging backwards without
rendering anything. Run `bl_anim_contact_sheet.py` for the half numbers cannot answer.
"""
import sys
import math

import bpy
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]

FPS = 30
IDENTITY = mathutils.Quaternion()
ZERO = mathutils.Vector((0.0, 0.0, 0.0))
WORLD = {
    "X": mathutils.Vector((1.0, 0.0, 0.0)),     # character's right
    "Y": mathutils.Vector((0.0, 1.0, 0.0)),     # character's front
    "Z": mathutils.Vector((0.0, 0.0, 1.0)),     # up
}
# sword_lowpoly.glb is 1.0 m from pommel butt to tip, blade along the socket's local +Y.
SWORD_LENGTH = 1.0


# ---------------------------------------------------------------------------- rig loading
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

scene = bpy.context.scene
scene.render.fps = FPS

arm = next((o for o in scene.objects if o.type == "ARMATURE"), None)
mesh_obj = next((o for o in scene.objects if o.type == "MESH"), None)
socket = bpy.data.objects.get("WeaponSocket")
if arm is None or mesh_obj is None:
    raise SystemExit("[anim] need one armature and one mesh in the input")
if socket is None:
    raise SystemExit("[anim] WeaponSocket is missing - re-run bl_normalize_rig.py")
if "Hips" not in arm.data.bones:
    raise SystemExit("[anim] bones are not humanoid-named - this is not a normalized rig")

BONES = [b.name for b in arm.data.bones]
REST = {b.name: b.matrix_local.copy() for b in arm.data.bones}
PARENT = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}


def depth(name):
    d = 0
    while PARENT[name] is not None:
        name = PARENT[name]
        d += 1
    return d


ORDER = sorted(BONES, key=depth)                 # parents always posed before their children
SOCKET_REST = socket.matrix_world.copy()
print(f"[anim] {len(BONES)} bones, socket rest at "
      f"{tuple(round(v, 3) for v in SOCKET_REST.translation)}")


# ------------------------------------------------------------------------------ pose math
class Pose:
    """One pose, built up bone by bone, with world axes resolved through the chain.

    Blender composes a posed bone as `pose_parent @ rest_parent^-1 @ rest @ basis`, so the
    3x3 part of everything left of `basis` is the map that takes a vector written in the
    bone's local frame out into armature space. Invert it and a world axis becomes the
    local axis to rotate about - which is the whole trick, and it keeps working when the
    parents are posed because their pose is inside that map.
    """

    def __init__(self):
        self.q = {}
        self.loc = {}

    def basis_map(self, name):
        parent = PARENT[name]
        if parent is None:
            return REST[name].copy()
        return self.world(parent) @ REST[parent].inverted() @ REST[name]

    def world(self, name):
        """The bone's posed matrix in armature space."""
        basis = (mathutils.Matrix.Translation(self.loc.get(name, ZERO))
                 @ self.q.get(name, IDENTITY).to_matrix().to_4x4())
        return self.basis_map(name) @ basis

    def delta(self, name):
        """What this bone does to anything rigidly attached to it at rest."""
        return self.world(name) @ REST[name].inverted()

    def rotate(self, name, ops):
        for kind, value in ops:
            base = self.basis_map(name)
            m3 = base.to_3x3()
            if kind == "loc":
                # A world-space offset of the bone, written into its local frame.
                self.loc[name] = (self.loc.get(name, ZERO)
                                  + m3.inverted() @ mathutils.Vector(value))
                continue
            if kind == "pivot":
                # Shift the bone so its rotation reads as happening about `value` instead
                # of about its own head - what makes the roll tumble around the tucked
                # body's centre rather than around the pelvis.
                q = self.q.get(name, IDENTITY)
                rot = m3 @ q.to_matrix() @ m3.inverted()
                arm_to_pivot = mathutils.Vector(value) - base.translation
                self.loc[name] = (self.loc.get(name, ZERO)
                                  + m3.inverted() @ (arm_to_pivot - rot @ arm_to_pivot))
                continue

            q = self.q.get(name, IDENTITY)
            current = m3 @ q.to_matrix()          # columns are the bone's world X, Y, Z
            if kind == "twist":
                axis = current.col[1]             # along the bone
            elif kind == "bend":
                axis = current.col[0]             # the normalizer's flexion axis
            else:
                axis = WORLD[kind]
            self.q[name] = mathutils.Quaternion(m3.inverted() @ axis,
                                                math.radians(value)) @ q


def layered(*layers):
    """Stack pose layers: a bone's ops from each layer run in the order the layers are given."""
    out = {}
    for layer in layers:
        for bone, ops in layer.items():
            out.setdefault(bone, []).extend(ops)
    return out


def build(spec):
    pose = Pose()
    for name in ORDER:
        if name in spec:
            pose.rotate(name, spec[name])
    return pose


def swap_sides(delta):
    """Exchange the character's left and right - the run's second half is its first.

    Reflecting through the sagittal plane leaves a sagittal (world X) rotation alone and
    reverses everything else, along with any sideways offset. Only the run uses this; the
    stance is asymmetric on purpose.
    """
    out = {}
    for bone, ops in delta.items():
        name = bone.replace("Left", "\0").replace("Right", "Left").replace("\0", "Right")
        flipped = []
        for kind, value in ops:
            if kind in ("loc", "pivot"):
                flipped.append((kind, (-value[0], value[1], value[2])))
            elif kind == "X":
                flipped.append((kind, value))
            else:
                flipped.append((kind, -value))
        out[name] = flipped
    return out


# -------------------------------------------------------------------------------- the poses
# The rest pose is a T-pose. STANCE is the character standing: arms brought down out of the
# T, the sword arm folded up into a guard with the blade vertical. Every clip layers on it.
#
# The right arm is the fiddly one. The socket's blade axis is perpendicular to the forearm
# (that is how a fist holds a grip), so a blade cannot point up while the arm hangs - it
# needs the elbow folded until the forearm is roughly horizontal, and then a wrist roll to
# bring the blade off horizontal and up. -90 is that roll; the residual tilt is about 1 deg.
STANCE = {
    "Spine":         [("X", -2)],
    "Chest":         [("X", -2)],
    "Neck":          [("X", 3)],

    "LeftUpperArm":  [("Y", -66), ("X", 6)],
    "LeftLowerArm":  [("X", 28)],
    "LeftHand":      [("twist", 15)],

    "RightUpperArm": [("Y", 62), ("X", 8)],
    "RightLowerArm": [("X", 80)],
    "RightHand":     [("twist", -90)],

    "LeftUpperLeg":  [("X", 2)],
    "LeftLowerLeg":  [("X", -6)],
    "LeftFoot":      [("X", 4)],
    "RightUpperLeg": [("X", 2)],
    "RightLowerLeg": [("X", -6)],
    "RightFoot":     [("X", 4)],
}

# --- idle: a 2 s breath. Small, but not so small it reads as a frozen mesh under a
# camera that never moves. The sword arm drifts on its own cycle so the two never line up.
IDLE = [
    (0, {}),
    (15, {
        "Spine":         [("X", 3)],
        "Chest":         [("X", 3)],
        "Neck":          [("X", -2)],
        "LeftUpperArm":  [("Y", -4)],
        "RightUpperArm": [("Y", 3), ("X", -4)],
        "Hips":          [("loc", (0.0, 0.0, 0.014))],
    }),
    (30, {
        "Spine":         [("X", -2)],
        "Chest":         [("X", -1)],
        "Hips":          [("Z", -3), ("loc", (0.008, 0.0, -0.006))],
        "LeftUpperArm":  [("X", 4)],
        "RightUpperArm": [("X", -6)],
        "RightLowerArm": [("X", 5)],
    }),
    (45, {
        "Spine":         [("X", 2)],
        "Chest":         [("X", 2)],
        "Neck":          [("X", -1)],
        "Hips":          [("Z", 2), ("loc", (-0.004, 0.0, 0.008))],
        "LeftUpperArm":  [("Y", -2)],
        "RightUpperArm": [("Y", 2), ("X", -2)],
    }),
    (60, {}),
]

# --- run: contact / down / airborne, then the same three with the sides exchanged.
# The sword arm swings less than the free arm - it is carrying a metre of steel.
#
# Swinging a straight leg forward lifts the foot faster than intuition suggests - the hip
# is only 0.88 m up and the leg is 0.74 m, so 34 degrees of thigh puts the foot 13 cm off
# the ground. With no root motion and no foot IK the planted foot slides anyway, so the
# bar here is simply that it must not visibly float: the report keeps the planted toe
# within a few centimetres of its rest height, and the amplitudes below are what that costs.
RUN_CONTACT = {
    "Hips":          [("Z", -7), ("loc", (0.0, 0.0, -0.008))],
    "Spine":         [("X", -9)],
    "Chest":         [("X", -3), ("Z", 14)],
    "LeftUpperLeg":  [("X", 22)],
    "LeftLowerLeg":  [("X", -10)],
    "LeftFoot":      [("X", 2)],
    "RightUpperLeg": [("X", -26)],
    "RightLowerLeg": [("X", -40)],
    "RightFoot":     [("X", 22)],
    "LeftUpperArm":  [("X", -34)],
    "LeftLowerArm":  [("X", 22)],
    "RightUpperArm": [("X", 20)],
    "RightLowerArm": [("X", -14)],
}
RUN_DOWN = {
    "Hips":          [("Z", -3), ("loc", (0.0, 0.0, -0.035))],
    "Spine":         [("X", -11)],
    "Chest":         [("X", -3), ("Z", 7)],
    "LeftUpperLeg":  [("X", 6)],
    "LeftLowerLeg":  [("X", -22)],
    "LeftFoot":      [("X", 14)],
    "RightUpperLeg": [("X", -32)],
    "RightLowerLeg": [("X", -58)],
    "RightFoot":     [("X", 28)],
    "LeftUpperArm":  [("X", -18)],
    "LeftLowerArm":  [("X", 30)],
    "RightUpperArm": [("X", 10)],
    "RightLowerArm": [("X", -6)],
}
RUN_AIR = {
    "Hips":          [("Z", -5), ("loc", (0.0, 0.0, 0.045))],
    "Spine":         [("X", -10)],
    "Chest":         [("X", -3), ("Z", 11)],
    "LeftUpperLeg":  [("X", -28)],
    "LeftLowerLeg":  [("X", -46)],
    "LeftFoot":      [("X", 26)],
    "RightUpperLeg": [("X", 16)],
    "RightLowerLeg": [("X", -66)],
    "RightFoot":     [("X", 30)],
    "LeftUpperArm":  [("X", -12)],
    "LeftLowerArm":  [("X", 34)],
    "RightUpperArm": [("X", 6)],
    "RightLowerArm": [("X", -4)],
}
RUN = [
    (0, RUN_CONTACT),
    (3, RUN_DOWN),
    (6, RUN_AIR),
    (9, swap_sides(RUN_CONTACT)),
    (12, swap_sides(RUN_DOWN)),
    (15, swap_sides(RUN_AIR)),
    (18, RUN_CONTACT),
]

# --- attack: a diagonal slash from over the right shoulder down across to the left.
# Impact is frame 8 of 15, i.e. 0.267 s in - that is where the Call Method track calling
# deal_attack_damage() goes when the clip is wired up in Godot.
ATTACK = [
    (0, {}),
    (4, {                                       # wind-up: coiled right, sword high and back
        "Hips":          [("Z", -14)],
        "Spine":         [("X", 3), ("Z", -12)],
        "Chest":         [("Z", -24)],
        # Y -115 against the stance's +62 puts the arm well above horizontal; anything less
        # and the wind-up just reads as the T-pose the rest pose already was. The +25 about
        # X then takes it *back* over the shoulder rather than out to the side - world +X
        # moves what is above a joint backward, and by now the arm is above the shoulder.
        "RightUpperArm": [("Y", -115), ("X", 25)],
        "RightLowerArm": [("X", -30)],
        "RightHand":     [("twist", 40)],
        "LeftUpperArm":  [("X", 30)],
        "LeftLowerArm":  [("X", 15)],
        "LeftUpperLeg":  [("X", -6)],
        "RightUpperLeg": [("X", 6)],
    }),
    (8, {                                       # impact: uncoiled left, blade out front
        "Hips":          [("Z", 14)],
        "Spine":         [("X", -16), ("Z", 12)],
        "Chest":         [("Z", 26)],
        "RightUpperArm": [("Y", 26), ("X", 42)],
        "RightLowerArm": [("X", -58)],
        "RightHand":     [("twist", -72)],
        "LeftUpperArm":  [("X", -28)],
        "LeftLowerArm":  [("X", 10)],
        "LeftUpperLeg":  [("X", 10)],
        "RightUpperLeg": [("X", -8)],
    }),
    (11, {                                      # follow-through: the blade keeps going left
        "Hips":          [("Z", 18)],
        "Spine":         [("X", -20), ("Z", 16)],
        "Chest":         [("Z", 34)],
        "RightUpperArm": [("Y", 56), ("X", 22)],
        "RightLowerArm": [("X", -70)],
        "RightHand":     [("twist", -95)],
        "LeftUpperArm":  [("X", -34)],
        "LeftUpperLeg":  [("X", 12)],
        "RightUpperLeg": [("X", -10)],
    }),
    (15, {}),
]

# --- roll: tuck into a ball and turn one full revolution forward.
# A forward roll takes the head down and forward, and world +X moves what is *above* a
# joint backward, so the revolution is about world -X. The clip is in-place, so the whole
# turn comes from the Hips - pivoted so the body tumbles around ROLL_PIVOT, roughly the
# centre of the tucked ball, instead of around the pelvis joint.
ROLL_PIVOT = (0.0, 0.15, 0.90)
TUCK = {
    "Spine":         [("X", -28)],
    "Chest":         [("X", -26)],
    "UpperChest":    [("X", -18)],
    "Neck":          [("X", -22)],
    "Head":          [("X", -14)],
    "LeftUpperLeg":  [("X", 112)],
    "LeftLowerLeg":  [("X", -132)],
    "LeftFoot":      [("X", 20)],
    "RightUpperLeg": [("X", 112)],
    "RightLowerLeg": [("X", -132)],
    "RightFoot":     [("X", 20)],
    "LeftUpperArm":  [("Y", -14), ("X", 46)],
    "LeftLowerArm":  [("X", 60)],
    "RightUpperArm": [("X", 40)],
    "RightLowerArm": [("X", 20)],
}


def tumble(degrees, drop, tuck=1.0):
    """The tucked body at `degrees` through the revolution, `drop` metres lower."""
    scaled = {bone: [(kind, value * tuck) for kind, value in ops] for bone, ops in TUCK.items()}
    return layered(scaled, {"Hips": [("X", degrees), ("pivot", ROLL_PIVOT),
                                     ("loc", (0.0, 0.0, drop))]})


# The last keyframe holds -360 rather than snapping back to 0: a key at 0 would make the
# f-curve unwind the whole revolution backwards over the final frames. -360 and 0 are the
# same orientation, and Godot's slerp handles the quaternion sign when blending out.
ROLL = [
    (0, {}),
    (3, tumble(-30, -0.30, tuck=0.85)),
    (7, tumble(-120, -0.42)),
    (11, tumble(-210, -0.42)),
    (15, tumble(-300, -0.38)),
    (18, tumble(-345, -0.18, tuck=0.55)),
    (21, {"Hips": [("X", -360)]}),
]

CLIPS = [
    ("idle", IDLE),
    ("run", RUN),
    ("attack", ATTACK),
    ("roll", ROLL),
]


# -------------------------------------------------------------------------------- authoring
def new_action(name):
    """A fresh Action assigned to the armature, with the slot Blender 4.4+ needs.

    Slotted actions mean an assigned Action animates nothing until a slot is bound to it.
    `keyframe_insert` will bind one implicitly, but doing it here keeps the action's name
    ours rather than whatever Blender autogenerates.
    """
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    arm.animation_data.action = action
    slots = getattr(action, "slots", None)
    if slots is not None:
        arm.animation_data.action_slot = slots.new(id_type="OBJECT", name=arm.name)
    return action


def report(label, pose):
    """World-space sanity numbers for one pose - the half of review that is free."""
    def at(bone):
        return pose.world(bone).translation

    socket = pose.delta("RightHand") @ SOCKET_REST
    blade = socket.col[1].to_3d().normalized()
    tip = socket.translation + blade * SWORD_LENGTH
    head, lf, rf = at("Head"), at("LeftToes"), at("RightToes")
    print(f"[anim]  {label:>4} head{head.z:+.2f} "
          f"toe L{lf.y:+.2f}/{lf.z:+.2f} R{rf.y:+.2f}/{rf.z:+.2f} "
          f"blade({blade.x:+.2f},{blade.y:+.2f},{blade.z:+.2f}) "
          f"tip({tip.x:+.2f},{tip.y:+.2f},{tip.z:+.2f})")


arm.animation_data_create()
for pose_bone in arm.pose.bones:
    pose_bone.rotation_mode = "QUATERNION"

for clip_name, keys in CLIPS:
    action = new_action(clip_name)
    print(f"[anim] {clip_name}: {len(keys)} keyframes, "
          f"{keys[-1][0]} frames ({keys[-1][0] / FPS:.2f}s)")
    for frame, delta in keys:
        pose = build(layered(STANCE, delta))
        for name in BONES:
            pose_bone = arm.pose.bones[name]
            pose_bone.rotation_quaternion = pose.q.get(name, IDENTITY)
            pose_bone.keyframe_insert("rotation_quaternion", frame=frame)
        # Only the Hips translate, and they translate in every clip, so the four clips
        # carry the same track set and the AnimationTree can blend any pair of them.
        hips = arm.pose.bones["Hips"]
        hips.location = pose.loc.get("Hips", ZERO)
        hips.keyframe_insert("location", frame=frame)
        report(f"f{frame}", pose)

    track = arm.animation_data.nla_tracks.new()
    track.name = clip_name
    track.strips.new(clip_name, 0, action)
    arm.animation_data.action = None

for track in arm.animation_data.nla_tracks:
    track.mute = True

# Godot names the imported MeshInstance3D after the Blender object, so without this the
# node inside knight_rigged.glb is called `knight_normalized` after the previous stage.
name = bpy.path.display_name_from_filepath(dst)
mesh_obj.name = name
mesh_obj.data.name = name + "Mesh"

print(f"[anim] {len(bpy.data.actions)} actions on "
      f"{len(arm.animation_data.nla_tracks)} NLA tracks")


# ---------------------------------------------------------------------------------- export
bpy.ops.export_scene.gltf(
    filepath=dst,
    export_format="GLB",
    export_apply=False,              # evaluating modifiers would flatten the armature
    export_yup=True,
    export_skins=True,
    export_animations=True,
    export_animation_mode="ACTIONS",  # one glTF animation per Action; Godot splits them
    export_frame_range=False,         # each action keeps its own length
    export_optimize_animation_size=False,   # keep every sampled key; the file is tiny
    export_bake_animation=False,
    export_current_frame=False,
    export_reset_pose_bones=True,
)
print(f"[anim] wrote {dst}")
