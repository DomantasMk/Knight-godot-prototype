# Conventions

Rules this codebase already follows, collected because they are scattered across files and
each one was paid for by a bug.

**Hand-written `.tscn`**
- `@export` node references do **not** reliably resolve at load time. Wire them from the
  owning entity's `_ready()` instead — that is why `tree.gd` assigns
  `_hurtbox.health_component` in code rather than in the inspector.
- Reference nodes inside a scene by unique name (`%Name`), not `$Path/To/Node`.

**Jolt physics**
- Collision shapes must stay **uniformly scaled** — non-uniform scale on a cylinder upsets
  Jolt. To squash something, scale a `Visuals` child holding only meshes, never the body.
- Never reshape a physics body from inside a physics callback: `set_deferred("disabled", …)`.

**Motion**
- Framerate-independent smoothing is `1.0 - exp(-speed * delta)`, never
  `lerp(a, b, speed * delta)` — the latter changes feel with framerate.
- Keep a tween in a member var and `kill()` it before starting a replacement, or
  spam-clicking stacks tweens on one property and they fight.

**Materials**
- A `PrimitiveMesh`'s material is shared by every instance of the scene. `duplicate()` it
  into a `material_override` before animating, or hitting one tree lights the whole forest.
- A GLB whose colour is in vertex colours imports **white**: Godot's glTF importer reads
  `COLOR_0` but never sets `vertex_color_use_as_albedo`. Point the asset's `.import` at
  `tools/import/vertex_color_material.gd`, which flips it once at import time.
- Deleting a `.glb.import` to force a reimport mints a **new UID**, silently orphaning the
  `ext_resource` in every scene that instanced it. Edit the file instead.

**Rigged assets** — more in [animation](animation.md)
- Bone-parent an empty in Blender and the glTF importer makes it a `BoneAttachment3D` for
  free. It is named after the **bone**, with the empty re-parented beneath
  (`Skeleton3D/RightHand/WeaponSocket`).
- Blender exports that empty's **rotation** in its own Z-up frame while converting everything
  around it, so it reaches Godot 90° out — sword through the knight's back, hanging below the
  hand. Its importer repeats the mistake in reverse, so Blender itself never shows it. The
  asset pipeline repairs the GLB on the way out and `verify_rigged_import.gd` asserts the
  result at rest; never compensate for it in a scene.
- Anything glTF cannot carry — loop modes, event tracks — goes in the asset's **import
  script**, never in the `.import` file's `_subresources`: one animation entry there makes
  Godot rewrite `slice_1..slice_100` of defaults per clip on every reimport, 279 KB of churn
  in a 1.2 KB file.

**Signals** — cross-system goes on `EventBus`; within one scene, connect directly.

_Files: exercised in entities/tree/tree.gd, and for the rigged rules entities/player/_
