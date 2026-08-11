# Stages 1–3 — reference image to a normalized rig

You are the `character-mesh-rig` agent. Your output is one file,
`local/rigging/work/<name>_normalized.glb`, plus a short report. Read `stages/traps.md` before
running any Blender step.

Write **only** into `local/rigging/work/` (and the Hunyuan3D install tree, which Stage 1's
scripts hardcode). Never touch a tracked repo file — Stage 5 is somebody else's job.

Keep every intermediate on disk when you finish. The next character change may re-enter at
Stage 3, and a deleted `_rigged.glb` means re-running the GPU stages for nothing.

---

## Stage 1 — a T-pose mesh

**The single most important constraint in this pipeline: generate the character in a
T-pose.** Auto-riggers need limbs visibly separated — arms horizontal, legs apart, clear air
at armpits and crotch. A mesh with arms fused to its torso cannot be rigged at all, and that
is a Stage 1 fix (reference image + voxel divisor), never something to patch downstream.

The `hunyuan3d` skill carries the operating detail. Two things that decide whether Stage 2
succeeds, both on that side:

- Build a **T-pose reference sheet** and prep the image before generating. Hunyuan3D
  reconstructs whatever is in the picture, labels and arrows included.
- `bl_process_vcol.py`'s voxel remesh **bridges any gap narrower than its own scale**, which
  is what welds arms to torsos. It takes optional trailing `voxel_divisor` (default 130) and
  `adaptivity_mult` (default 2.0); the knight was built at `190 1.5` (1.05 cm voxel). Finer
  voxels cost pre-decimation triangles only — `target_tris` still sets the final count.

Budget: **~6–8k triangles** for a player-facing character. Only the player pays that; scenery
stays far cheaper. Colour lives in `COLOR_0` vertex colours with the UVs deleted, because a
baked UV atlas puts a hard floor under decimation (~9.3k tris) that no amount of iterating
gets past.

**Gate: look at the preview.** A bad crop or a fused armpit costs a full generation cycle to
discover at Stage 2.

**Budget your own context here.** This is a regenerate-and-look loop and each preview read
costs ~250–1000 tokens depending on the render size. Keep previews small, look once per
generation, and decide — do not collect a gallery. If you are past ~120k, report what you have
and say a re-spawn is needed rather than pushing into a truncation.

## Stage 2 — rig it

```powershell
Push-Location $env:SKINTOKENS_DIR
& $env:SKINTOKENS_PY "$env:SKINTOKENS_DIR\demo.py" `
    --input <in.glb> --output <out.glb> --use_transfer --use_postprocess
Pop-Location
```

Run from the install root — it resolves configs and checkpoints relatively. `--use_transfer`
re-exports the *original* mesh with weights mapped across, which is what preserves `COLOR_0`;
`--use_postprocess` refines the skin weights. ~2 minutes, 7–11 GB VRAM.

**Gate — inspect the skeleton, do not assume it:**

```powershell
py -3.11 tools/rigging/glb_inspect.py <out.glb> --require skin,color,joints --tree
```

`--tree` prints the joint hierarchy with rest positions. Predicted names are generic
(`bone_0`…) and carry no information at all, so a skeleton can only be judged by **shape and
position**: is it symmetric, does the hierarchy branch where a body branches, do the joints
sit on real anatomy.

- Clean humanoid → Stage 3.
- Messy → author a humanoid armature in Blender and re-run with `--use_skeleton`, which skips
  prediction and skins the armature you supply. Same tool, one flag, and *strictly better* for
  Stage 4 because every bone name, axis and roll becomes deterministic instead of discovered.

**Do not generalise from one subject.** The bundled giraffe rigs to 47 generic bones and looks
hopeless; the knight came back textbook. A quadruped says nothing about a biped.

## Stage 3 — normalize the rig

```powershell
& $env:BLENDER_BIN -b -P tools/rigging/bl_normalize_rig.py -- <rigged.glb> <normalized.glb>
```

SkinTokens predicts a good skeleton and bad metadata. This script fixes the metadata, in an
order that matters:

1. **Names bones by hierarchy and position, never by name** — a child of the hips on the
   character's +X side is the left leg, whatever it is called. Every assumption is asserted,
   so a differently-shaped skeleton fails loudly here instead of producing a silently
   mislabelled rig. Names follow `SkeletonProfileHumanoid`, which keeps external clips
   possible later without anything depending on it.
2. **Turns the character 180°** to face Godot-forward. Naming runs first, because after the
   turn the character's left is no longer on +X.
3. **Rebuilds tails and rolls** so every bone's local Z faces the character's front, making
   local X the flexion axis on the whole skeleton. This is the difference between authoring
   Stage 4 and guessing at 30 bones' axes one at a time. Editing rest orientation does not
   deform the mesh — at rest, pose × rest⁻¹ is identity whatever the tail does.
4. **Adds a socket empty, bone-parented to a hand.** Godot's glTF importer turns a
   bone-parented node into a `BoneAttachment3D` by itself, which is what lets a weapon hang
   off a hand bone from a hand-written `.tscn` with no editable children.

**Per character, edit:** `GRIP_INSET` (where the weapon's own origin sits relative to the
fist) and the socket's bone and orientation. A character with no weapon can drop step 4; one
with two weapons needs two empties.

**The grip is deliberately perpendicular to the forearm** — that is how a fist holds a handle.
Its consequence shapes every pose: a blade *cannot* point up while the arm hangs down, because
it is confined to the plane perpendicular to the forearm. Any pose wanting the blade somewhere
specific has to move the **elbow**, not just the wrist. This is not a bug to fix, and Stage 4
needs to be told about it — say so in your report.

---

## What to report back

Twenty lines, no more. The orchestrator uses it to brief Stage 4 and to wire Stage 5:

- the path to `<name>_normalized.glb`, and that the intermediates are still on disk
- bone count, and the humanoid names assigned (list them if they deviate from the profile)
- the socket's bone and its rest position
- the `glb_inspect --require skin,color,joints` result, and the final triangle count
- character height and, if it holds one, weapon length — Stage 4 calibrates gates off these
- anything you had to deviate on, and anything Stage 4 should know about the grip plane

Do not paste the joint tree, the Blender log, or the generation transcript. If the orchestrator
needs a detail you left out it will message you, and your context is still warm.
