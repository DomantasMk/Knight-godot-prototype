"""Blender headless: render every animation clip in a GLB as one contact sheet.

    blender -b -P bl_anim_contact_sheet.py -- <input.glb> <output.png>
                                              [frames_per_clip] [cell_w] [cell_h]

One row per clip, `frames_per_clip` evenly-spaced poses across it, all composited into a
single PNG. The row order is printed to stdout, because drawing text into the sheet would
need font handling for no real gain.

Why one image and not a folder of renders: reviewing animation means looking at it, and
every look costs tokens that then ride along for the rest of the session (see the
screenshot-budget rule in CLAUDE.md). A four-clip sheet answers "do these poses read" in
one image instead of twenty-four, so the defaults here are deliberately small - this is a
silhouette check, not a beauty render.

The camera sits three-quarter front, on the character's own right, so the sword arm is the
one nearest the lens: a pure front view hides the depth of a swing, and a pure side view
hides which arm is doing it. "Front" here means **+Y** - `bl_normalize_rig.py` turns the
character to face Godot-forward, which is the opposite of Blender's usual -Y convention.
"""
import sys
import math

import bpy
import mathutils
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]
per_clip = int(argv[2]) if len(argv) > 2 else 6
cell_w = int(argv[3]) if len(argv) > 3 else 200
cell_h = int(argv[4]) if len(argv) > 4 else 250

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
if not armatures:
    raise SystemExit("[sheet] no armature in the file - nothing to animate")
arm = armatures[0]

# The glTF importer parks each imported animation in an NLA track on the armature. Reading
# the actions back off those strips is the only way to enumerate clips by name.
actions = []
seen = set()
for track in (arm.animation_data.nla_tracks if arm.animation_data else []):
    for strip in track.strips:
        if strip.action and strip.action.name not in seen:
            seen.add(strip.action.name)
            actions.append(strip.action)
if not actions:
    # Single-clip files leave the action assigned directly instead of stashing it.
    if arm.animation_data and arm.animation_data.action:
        actions = [arm.animation_data.action]
    else:
        raise SystemExit("[sheet] armature has no actions")

# Muting the tracks stops them stacking on top of whatever action we assign below.
for track in (arm.animation_data.nla_tracks if arm.animation_data else []):
    track.mute = True

# --- framing ------------------------------------------------------------------
# Frame off the rest pose and then pad generously: a swing or a roll throws limbs well
# outside the idle silhouette, and a clipped sword tip is exactly what needs reviewing.
mn = mathutils.Vector((1e9,) * 3)
mx = mathutils.Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        mn = mathutils.Vector((min(mn[i], w[i]) for i in range(3)))
        mx = mathutils.Vector((max(mx[i], w[i]) for i in range(3)))
center = (mn + mx) / 2
size = max((mx - mn)[i] for i in range(3))

world = bpy.data.worlds.new("W")
bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[1].default_value = 1.2

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", type="SUN"))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(55), 0, math.radians(35))
bpy.context.scene.collection.objects.link(sun)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = cell_w
scene.render.resolution_y = cell_h
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.collection.objects.link(cam)
scene.camera = cam
a = math.radians(35.0)                      # three-quarter front, over the sword shoulder
r = size * 1.9
cam.location = (center.x + r * math.sin(a), center.y + r * math.cos(a), center.z + size * 0.25)
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

# --- render every pose into one array -----------------------------------------
sheet = np.zeros((cell_h * len(actions), cell_w * per_clip, 4), dtype=np.float32)
sheet[..., 3] = 1.0
tmp = bpy.app.tempdir + "cell.png"

for row, action in enumerate(actions):
    arm.animation_data.action = action
    start, end = action.frame_range
    # glTF stores keyframe times in seconds and the importer converts them at whatever fps
    # the scene happens to be on, so these frame numbers will not match the ones the clip
    # was authored at. Seconds are the number that survives the round trip.
    print(f"[sheet] row {row}: {action.name!r} frames {start:.0f}-{end:.0f} "
          f"({(end - start) / scene.render.fps:.2f}s at {scene.render.fps} fps)")
    for col in range(per_clip):
        t = col / max(1, per_clip - 1)
        scene.frame_set(int(round(start + t * (end - start))))
        scene.render.filepath = tmp
        bpy.ops.render.render(write_still=True)

        img = bpy.data.images.load(tmp)
        # Blender's buffer is bottom-up, so flip it to get a top-down sheet.
        cell = np.array(img.pixels[:], dtype=np.float32).reshape(cell_h, cell_w, 4)[::-1]
        bpy.data.images.remove(img)
        sheet[row * cell_h:(row + 1) * cell_h, col * cell_w:(col + 1) * cell_w] = cell

out = bpy.data.images.new("sheet", width=sheet.shape[1], height=sheet.shape[0], alpha=True)
out.pixels = sheet[::-1].ravel()            # flip back into Blender's bottom-up order
out.filepath_raw = dst
out.file_format = "PNG"
out.save()

print(f"[sheet] wrote {dst} {sheet.shape[1]}x{sheet.shape[0]} "
      f"rows(top to bottom)={[a.name for a in actions]}")
