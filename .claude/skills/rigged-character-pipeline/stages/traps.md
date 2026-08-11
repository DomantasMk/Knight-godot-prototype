# Traps, all paid for once

Read this before running any Blender step. Every entry here cost a debugging session.

## Blender

1. **`bone.children` returns a fresh Python wrapper on every RNA access.** Two reads of the
   same collection give objects that compare `==` but not `is`, so filtering an identity out
   of a *second* read silently keeps it. Filter by `.name` — `bl_normalize_rig.py` has an
   `excluding()` helper.
2. **`bpy.ops.object.transform_apply` silently does nothing** on an armature with a parented
   mesh, and reports success either way. Transform the datablocks directly:
   `mesh.data.transform(M)` and `EditBone.transform(M)` in edit mode.
3. **Blender 4.4+ has slotted actions.** An Action assigned to an object animates nothing
   until a slot is bound. `hasattr(bpy.types.Action, "slots")` returns **False** while
   `action.slots` on an *instance* works — the properties are RNA, not Python attributes, so
   probe instances, never the type.
4. **Blender 5.2's only render engine is `BLENDER_EEVEE`**, not the 4.2–4.5 `BLENDER_EEVEE_NEXT`.
5. The contact-sheet camera assumes the character faces **+Y** (post-normalize). Blender's
   usual convention is −Y, and getting it wrong renders the character's back.

## Everywhere

- Keep printed strings **ASCII**. The Windows console is cp1252 and mangles em-dashes.
- **Never pipe pip through `tail`/`head`** — the shell reports the pipe's exit status, so a
  failed install reads as success.
- Add a `.gdignore` to any scratch directory inside the project, or Godot reimports every
  contact sheet on each `--headless --import`.
- Blender and the GPU stages are slow. Run them with a generous timeout rather than letting a
  call time out and re-running — a re-run costs the whole stage again.

## Known rough edges

Honest about what "it worked" meant on the first run through the knight:

- Motion is hand-authored keyframes, and it reads as hand-authored keyframes. That was the
  accepted trade for a fully-local pipeline with no mocap dependency; the contact-sheet loop
  is what keeps iterating on it cheap.
- `LeftFoot`/`RightFoot` normalize with local Y at ≈35° off horizontal, so the ankle's neutral
  is slightly toe-down. Harmless for in-place clips. Revisit only if footplant reads wrong.
- Swinging a straight leg forward lifts the foot fast — 34° of thigh is 13 cm off the ground —
  so run-cycle amplitudes need to be much smaller than they look on paper.
- Most of the Stage 4 tuning time went into the sword arm, because of the perpendicular grip.
  Budget for that on any character holding something.
