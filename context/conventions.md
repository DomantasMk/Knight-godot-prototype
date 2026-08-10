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

**Signals** — cross-system goes on `EventBus`; within one scene, connect directly.

_Files: every rule above is exercised in entities/tree/tree.gd_
