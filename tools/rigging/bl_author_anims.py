"""Blender headless: author a character's animation clips on its normalized rig.

    blender -b -P bl_author_anims.py -- <normalized.glb> <animated.glb> [spec]

`spec` names a `clips_<spec>.py` module next door and defaults to `knight`. **That module is
where the per-character constants live** - the stance, the clip poses, the clip registry and
the weapon length. This file is the machinery: the pose maths, the keyframe writer, the report
and the export. Do not put a number about one character in here.

The vocabulary those specs are written in - world axes, `twist`/`bend`, `loc`/`pivot`,
layering, mirroring and the easing modes - is documented in `pose_ops.py`.

Input is `<name>_normalized.glb` from `bl_normalize_rig.py`, not the raw SkinTokens
output - **or this script's own output**, i.e. the shipped `assets/models/knight_rigged_v2.glb`.
Both carry the same normalized rest pose, and the second is the only one that still exists:
`local/rigging/work/` is gitignored and was cleaned up after the knight shipped, which would
otherwise make adding a fifth clip a full re-run from Stage 1 and a different knight. Any
imported animation is therefore dropped on load - see `strip_animation()` for why that is
not merely tidiness.

Every clip is authored as scripted keyframes - there is no mocap library and no retarget
step, because the motion is written directly onto the rig that will play it. One Action each,
stashed on NLA tracks so both the glTF exporter (Animation Mode = Actions) and
`bl_anim_contact_sheet.py` can find them.

## How a pose becomes a keyframe

`Pose` goes one step further than reading an axis off the bone's *rest* matrix. That is only
a world axis while the bone's parents are unposed: once the shoulder is rotated 70 degrees to
bring the arm down out of its T-pose, the forearm's rest X is no longer world X, and "bend the
elbow forward" stops meaning that. `Pose` therefore carries the accumulated pose down the
chain, so an axis named in a spec is the true world axis no matter what the parents are doing.

## Reading the report

The script prints, for every keyframe it writes, the world position of the head, hands and
feet and the direction the sword blade points. That is the cheap half of reviewing an
animation - it catches a foot through the floor or a sword swinging backwards without
rendering anything.

It is only half, though, and the missing half is **spacing**: a pose report says where the
blade is, never how fast it got there. The knight's first swing passed every pose check and
still landed its hit on the slowest frame of the strike. Run
`tools/rigging/blade_speed.py --gates` on the exported GLB for that, and
`bl_anim_contact_sheet.py` for the half numbers cannot answer at all.
"""
import importlib
import os
import sys
import math

import bpy
import mathutils

# Blender does not put a `-P` script's own directory on sys.path, and the socket repair this
# script ends with - plus the pose helpers and the clip spec - all live next door.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glb_fix_socket import fix_socket                                          # noqa: E402
from pose_ops import layered, unpack_key                                       # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]
spec_name = argv[2] if len(argv) > 2 else "knight"
spec = importlib.import_module(f"clips_{spec_name}")

FPS = 30
IDENTITY = mathutils.Quaternion()
ZERO = mathutils.Vector((0.0, 0.0, 0.0))
WORLD = {
    "X": mathutils.Vector((1.0, 0.0, 0.0)),     # character's right
    "Y": mathutils.Vector((0.0, 1.0, 0.0)),     # character's front
    "Z": mathutils.Vector((0.0, 0.0, 1.0)),     # up
}
STANCE = spec.STANCE
CLIPS = spec.CLIPS
SWORD_LENGTH = spec.SWORD_LENGTH


# ---------------------------------------------------------------------------- rig loading
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

scene = bpy.context.scene
scene.render.fps = FPS


def strip_animation():
    """Leave the rig exactly as an un-animated normalized rig would arrive.

    Only does anything when the input is a previously animated GLB, and then it does three
    things that all matter. Clearing `animation_data` drops the NLA tracks, or the export
    would ship each clip twice. Removing the Actions frees their names, or `actions.new()`
    would quietly hand back `idle.001` and the clip Godot looks up by name would not exist.
    Resetting the pose bones matters most: the exporter samples every bone's location,
    rotation and scale, so a channel this script never keys - every bone but the Hips, for
    location - would otherwise export whatever pose the importer happened to leave behind.
    """
    for obj in scene.objects:
        if obj.animation_data is not None:
            obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    for obj in scene.objects:
        if obj.type == "ARMATURE":
            for bone in obj.pose.bones:
                bone.matrix_basis.identity()


strip_animation()

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

# The socket's rest matrix is restated, not read off the imported empty. Blender's glTF
# importer mis-reads a bone-parented node - `glb_fix_socket.py` has the whole story - and on
# a re-run over this script's own repaired output, which is the documented way to add a clip,
# the socket arrives lying on its side about 30 cm from the fist. The exported file is not
# affected, since the matching exporter bug puts it back, but every blade direction and sword
# tip reported below would be nonsense, and this report is the cheap half of the review.
#
# Restated is bl_normalize_rig.py's own rule: the fist is the midpoint between the hand bone
# and its index-finger child - which is exactly where that script points the hand's tail, and
# unlike a tail it survives the import, because the importer reinvents tails and keeps heads.
GRIP_INSET = 0.18                                # must match bl_normalize_rig.py
SOCKET_BLADE_UP = mathutils.Matrix((
    (1.0, 0.0, 0.0),
    (0.0, 0.0, -1.0),
    (0.0, 1.0, 0.0),
)).to_4x4()                                      # socket local +Y -> world +Z, i.e. blade up


def head_of(bone):
    return arm.matrix_world @ arm.data.bones[bone].head_local


FIST = head_of("RightHand").lerp(head_of("RightIndexProximal"), 0.5)
SOCKET_REST = mathutils.Matrix.Translation(FIST - WORLD["Z"] * GRIP_INSET) @ SOCKET_BLADE_UP
print(f"[anim] {len(BONES)} bones, socket rest at "
      f"{tuple(round(v, 3) for v in SOCKET_REST.translation)}")
_drift = (socket.matrix_world.translation - SOCKET_REST.translation).length
if _drift > 0.001:
    print(f"[anim] (the importer put the socket {_drift:.3f} m away, at "
          f"{tuple(round(v, 3) for v in socket.matrix_world.translation)} - mis-read, "
          f"not a rig problem; the export is unaffected)")


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


def build(pose_spec):
    pose = Pose()
    for name in ORDER:
        if name in pose_spec:
            pose.rotate(name, pose_spec[name])
    return pose


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
    slot = None
    slots = getattr(action, "slots", None)
    if slots is not None:
        slot = slots.new(id_type="OBJECT", name=arm.name)
        arm.animation_data.action_slot = slot
    return action, slot


def fcurves_of(action, slot):
    """The Action's f-curves, whichever layout this Blender uses.

    4.4 moved them out of `action.fcurves` and into a channel bag under the action's slot,
    which is why this is not a one-liner. Nothing else in this script needs to reach them -
    `keyframe_insert` creates them - but easing is a property *of the curve*, not of the pose.
    """
    layers = getattr(action, "layers", None)
    if layers and slot is not None:
        for layer in layers:
            for strip in layer.strips:
                getter = getattr(strip, "channelbag", None)
                if getter is None:
                    continue
                try:
                    bag = getter(slot)
                except TypeError:
                    bag = getter(slot, ensure=False)
                if bag is not None and len(bag.fcurves):
                    return bag.fcurves
    return getattr(action, "fcurves", [])


def apply_easing(action, slot, easing_by_frame):
    """Set interpolation and easing on every curve's keys, by frame.

    Done in one pass at the end rather than after each `keyframe_insert`, because a pose
    writes 147 curves and the frame is the only thing that identifies a key across them.

    Returns the number of keyframe points touched, and the caller treats zero as fatal. A
    silent no-op here is the worst outcome available: the clip exports looking authored, the
    default auto-Bezier easing is still baked into every sampled frame, and the swing
    decelerates into its own impact exactly as it did before anyone tried to fix it.
    """
    if not easing_by_frame:
        return 0
    touched = 0
    for fcurve in fcurves_of(action, slot):
        for point in fcurve.keyframe_points:
            ease = easing_by_frame.get(round(point.co[0]))
            if ease is None:
                continue
            point.interpolation, point.easing = ease
            touched += 1
        fcurve.update()
    return touched


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

for clip_name, clip_keys in CLIPS:
    action, slot = new_action(clip_name)
    keys = [unpack_key(key) for key in clip_keys]
    print(f"[anim] {clip_name}: {len(keys)} keyframes, "
          f"{keys[-1][0]} frames ({keys[-1][0] / FPS:.2f}s)")
    for frame, delta, _ease in keys:
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

    # Keys with no `ease` keep Blender's default auto-clamped Bezier, which is what every
    # clip but `attack` wants: none of them has one frame that has to be the fastest.
    easing = {frame: ease for frame, _delta, ease in keys if ease is not None}
    if easing:
        touched = apply_easing(action, slot, easing)
        if touched == 0:
            raise SystemExit(f"[anim] {clip_name}: asked for easing on {sorted(easing)} and "
                             "set none - fcurves_of() found no curves, so the clip would "
                             "have exported with its default easing silently intact")
        print(f"[anim] {clip_name}: easing on frames {sorted(easing)}, "
              f"{touched} keyframe points set")

    track = arm.animation_data.nla_tracks.new()
    track.name = clip_name
    track.strips.new(clip_name, 0, action)
    arm.animation_data.action = None

for track in arm.animation_data.nla_tracks:
    track.mute = True

# Godot names the imported MeshInstance3D after the Blender object, so without this the
# node inside the shipped GLB would be called `knight_normalized` after the previous stage.
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

# The exporter writes a bone-parented object's rotation in Blender's own Z-up frame while
# converting its translation to Y-up, so the socket reaches Godot rotated 90 degrees about X:
# blade out of the knight's back, grip inset dropping the sword below the hand rather than
# into it. Repaired here because this is the last thing that touches the file - a corrected
# GLB read back into Blender is mis-read by the matching importer bug, so the correction
# cannot be made any earlier in the chain. The wanted orientation is stated rather than
# measured off the scene for the same reason.
fix_socket(dst)
