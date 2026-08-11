---
name: generated-3d-assets
description: Use when bringing a generated or externally authored 3D model into KnightPrototype — importing a GLB, wiring it into an entity scene, sizing collision, and the material handling the hit-flash requires. Covers both flat-shaded and textured variants.
---

# Generated 3D assets in KnightPrototype

Getting a generated mesh (Hunyuan3D or similar image-to-3D tooling) into this project.

**Scope: the Godot side only.** Generating the mesh and decimating it to a GLB is a
separate, machine-local concern — see the user-level `hunyuan3d` skill for the pipeline,
version pins, and the colour-space and UV-floor traps. This skill starts from a finished
GLB.

Per `CLAUDE.md`, also invoke `godot-prompter:assets-pipeline` before import work.
Tool paths (the Godot binary in particular) are in `CLAUDE.md` under Commands.

Worked example already in the repo: `entities/tree/`.

## Import

Models go in `assets/models/` — per the layout rule, `assets/` stays sorted by type
rather than co-located with the feature.

```powershell
Copy-Item <path-to>\<name>.glb .\assets\models\ -Force
& $godot --path . --headless --import
```

Then read the generated `assets/models/<name>.glb.import` for its `uid=` line — the
entity scene references the asset by UID, and it differs per file.

**Commit the `.import` file. Never commit `.godot/`.**

**A GLB coloured by vertex colours imports white.** Godot's glTF importer reads `COLOR_0`
into the mesh but never sets `StandardMaterial3D.vertex_color_use_as_albedo`, so the data
is there and unused. Point the asset's `.import` at the project's import script:

```
import_script/path="res://tools/import/vertex_color_material.gd"
```

Do this by **editing** the `.import` file. Deleting it to force a reimport mints a new UID
and silently orphans the `ext_resource` in every scene that instanced the model.

A textured GLB also makes Godot extract its embedded image as a sibling
`<name>_Image_0.png` (+ `.import`). Those belong to the asset — delete or commit them
together with it, not separately.

## Wiring into an entity scene

Instance the imported GLB under the entity's `Visuals` node. Hand-written `.tscn`, so
per `context/conventions.md`:

- `load_steps` must equal `ext_resource` + `sub_resource` count **plus one**.
- Reference nodes by unique name (`%Name`), never `$Path/To/Node`.

```
[ext_resource type="PackedScene" uid="uid://<from the .import file>" path="res://assets/models/<name>.glb" id="4_model"]

[node name="Visuals" type="Node3D" parent="."]
unique_name_in_owner = true

[node name="Model" parent="Visuals" instance=ExtResource("4_model")]
```

Do **not** put `unique_name_in_owner` on nodes inside the instanced GLB — they belong to
the imported asset, not the entity scene, and will not survive a reimport.

Author assets with their origin at the base centre so the entity sits at y=0 with no
transform on the `Model` node. If a model arrives origin-centred, fix it in the authoring
tool rather than offsetting the node — a transform here fights the scatter code.

## Rigged assets

Worked example: `entities/player/` against `assets/models/knight_rigged_v2.glb`.

**If you are producing the rig and clips too, not just importing them, use the
`rigged-character-pipeline` skill instead** — it covers all five stages and this is its last
one. Everything below is the Godot side alone. Read `context/animation.md` first; per
`CLAUDE.md`, also invoke `godot-prompter:animation-system` before touching an `AnimationTree`.

**A model exported the ordinary way from Blender arrives facing backwards.** Blender
characters face -Y, the glTF exporter writes that as +Z, and a `Node3D`'s forward is -Z. Fix
it in the rig (`bl_normalize_rig.py` bakes the 180° into the mesh *and* the rest bones), never
with a correction transform on `Visuals` or `Model` — a later asset fix then cancels against it.

**Sockets are free if you bone-parent an empty in Blender.** Godot's glTF importer converts
it into a `BoneAttachment3D`, so nothing has to be wired in `_ready()`. The generated node is
named after the **bone**, and your empty is re-parented beneath it:

```
[node name="Sword" parent="Visuals/Model/Armature/Skeleton3D/RightHand/WeaponSocket" instance=ExtResource("4_sword")]
```

Give the attached node **no transform of its own** — the socket carries the whole grip, and a
compensating transform here means the next re-export fights it. Descending into the instance
this way needs an `[editable path="Visuals/Model"]` line at the end of the `.tscn`.

**The `AnimationTree` goes in the entity scene, and its `root_node` must resolve to the
model** — not to the entity root. Every bone track's path is relative to `root_node`; point it
one level too high and all of them fail to resolve, with no error and no animation.

```
[node name="AnimationTree" type="AnimationTree" parent="."]
unique_name_in_owner = true
root_node = NodePath("../Visuals/Model")
tree_root = SubResource("StateMachine_player")
anim_player = NodePath("../Visuals/Model/AnimationPlayer")
active = true
```

**glTF carries no loop modes and no event tracks.** Both go in the asset's import script
(`tools/import/knight_rigged_import.gd` extends the vertex-colour one and adds them), *not*
in the `.import` file's `_subresources` — a single animation entry there makes Godot rewrite
`slice_1..slice_100` of defaults per clip on every reimport, 279 KB of churn in a 1.2 KB file.

A Call Method track resolves its target through the **mixer's** `root_node`, which is the
`AnimationTree`, which points at the model — so `NodePath("../..")` reaches the entity root.
That path encodes the scene's shape; assert it rather than trusting it.

Leave `animation/remove_immutable_tracks=false` when clips key every bone. A bone holding a
constant *non-rest* value for a whole clip looks immutable, and dropping its track snaps that
bone back to rest for the entire clip.

## Materials: the part that breaks silently

The hit-flash needs a **per-instance** material copy, or striking one entity lights up
every instance of that scene. Two things about imported meshes make the greybox approach
fail:

1. An imported mesh is an `ArrayMesh`, not a `PrimitiveMesh` — code reading
   `(mesh as PrimitiveMesh).material` falls through to a blank white material, and the
   asset renders white.
2. `material_override` replaces **all** surfaces at once. Generated meshes usually carry
   several (e.g. bark + foliage), so one override collapses the model to a single colour.

Use per-surface overrides, and walk the imported subtree rather than naming its nodes:

```gdscript
func _find_mesh_instances(root: Node) -> Array[MeshInstance3D]:
	var found: Array[MeshInstance3D] = []
	for child in root.get_children():
		if child is MeshInstance3D:
			found.append(child)
		found.append_array(_find_mesh_instances(child))
	return found


func _make_flashable_materials(mesh_instance: MeshInstance3D) -> Array[StandardMaterial3D]:
	var made: Array[StandardMaterial3D] = []
	if mesh_instance.mesh == null:
		return made

	for surface in mesh_instance.mesh.get_surface_count():
		var source := mesh_instance.get_active_material(surface) as StandardMaterial3D
		var material: StandardMaterial3D = source.duplicate() if source else StandardMaterial3D.new()
		material.emission_enabled = true
		material.emission = Color.WHITE
		material.emission_energy_multiplier = 0.0
		mesh_instance.set_surface_override_material(surface, material)
		made.append(material)
	return made
```

This works unchanged for flat-shaded and textured variants.

## Collision — resize it, do not inherit it

Greybox primitives and imported models rarely share dimensions. The greybox tree was
~5 m tall and the imported one is 3.5 m, so the original 4 m collider and a hurtbox
reaching above the canopy were both wrong.

Size shapes to the **imported** model, and keep the Jolt rule from
`context/conventions.md`: collision shapes stay **uniformly scaled**. To squash
something, scale a `Visuals` child holding only meshes — never the body.

Reference values for the 3.5 m tree:

| Shape | Height | Radius | Y offset |
|---|---|---|---|
| `TrunkCollision` | 1.8 | 0.32 | 0.9 |
| `Hurtbox` | 3.5 | 1.0 | 1.75 |

`level_01.gd` scales scattered trees `0.85–1.2` uniformly, so author assets at their
real height and let the level vary them.

## Verify — always, and visually

```powershell
& $godot --path . --headless --quit-after 120     # parse/load errors, expect exit 0
```

A clean headless run does **not** mean the asset looks right. Render actual frames:

```powershell
& $godot --path . --write-movie <scratch>\f.png --quit-after 45 --resolution 1280x720
```

Then open the last frame. Wrong-coloured, wrong-scaled, and white-flashed assets all
pass the headless check.

**Cheaper than a screenshot: assert it.** Screenshots cost ~250 tokens that then ride along
for the whole session, so the checks a number can answer are scripted instead. The rigged
knight has two gates, both exiting non-zero on failure — copy the shape for a new asset:

```powershell
& $godot --path . --headless --script res://tools/rigging/verify_rigged_import.gd   # the asset
& $godot --path . --headless --script res://tools/rigging/verify_player_scene.gd    # the seam
```

The first checks per-surface vertex-colour albedo, bone names, clip durations and loop modes,
and the impact track. The second instantiates the entity, walks it into the tree, advances the
`AnimationTree` by hand through the attack clip and checks the strike actually fires — the
kind of failure that plays perfectly and deals zero damage. Keep the picture for the questions
a number cannot answer.

## Choosing flat vs textured in this project

The fixed overhead camera views props at 3–4 m. At that distance a baked albedo reads as
speckle and loses the faceted silhouette, while costing roughly 10× the triangles and a
multi-MB embedded texture per instance — a baked UV atlas also puts a hard floor under
decimation, because collapse cannot merge across island seams. `level_01` additionally
lights everything brightly (sky-based ambient IBL + directional + filmic tonemap), which
flattens baked shading further.

**For a multi-coloured asset, the third option beats both.** The knight and sword are
generated *textured*, then the albedo is baked down to vertex colours and the UVs deleted,
which removes the decimation floor entirely — the knight is 2.7k triangles with its steel,
blue tabard and gold trim intact, and no embedded texture at all. That path needs the
import script above. Use it whenever a prop has more than two colour regions; the
height-split flat-material trick only works on things as simple as a tree.

**Otherwise default to flat-shaded props here.** Both variants of the tree are in
`assets/models/`; switching is a one-line `ext_resource` change in
`entities/tree/tree.tscn`.

If colours read lighter in-game than in an external preview render, that is this level's
lighting, not the asset — do not "fix" it in the material without saying so.
