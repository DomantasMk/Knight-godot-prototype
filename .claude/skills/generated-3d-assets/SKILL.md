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

## Choosing flat vs textured in this project

The fixed overhead camera views props at 3–4 m. At that distance a baked albedo reads as
speckle and loses the faceted silhouette, while costing roughly 10× the triangles and a
multi-MB embedded texture per instance — a baked UV atlas also puts a hard floor under
decimation, because collapse cannot merge across island seams. `level_01` additionally
lights everything brightly (sky-based ambient IBL + directional + filmic tonemap), which
flattens baked shading further.

**Default to flat-shaded props here.** Both variants of the tree are in
`assets/models/`; switching is a one-line `ext_resource` change in
`entities/tree/tree.tscn`.

If colours read lighter in-game than in an external preview render, that is this level's
lighting, not the asset — do not "fix" it in the material without saying so.
