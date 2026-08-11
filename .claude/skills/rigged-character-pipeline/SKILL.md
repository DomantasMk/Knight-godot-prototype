---
name: rigged-character-pipeline
description: Use when taking a character from nothing to a rigged, animated, playable entity in KnightPrototype — generating or rigging a humanoid mesh, predicting a skeleton, normalizing bone names and rolls, authoring animation clips in Blender, and wiring the result into a Godot scene with an AnimationTree. Covers the five-stage local pipeline, what to change per character, and the traps each stage hides. Triggers on "rig this model", "animate a character", "new enemy/character asset", "add animations to", "model to rig to animation".
---

# The rigged-character pipeline

Takes a humanoid mesh to a rigged, animated entity in this project. **Fully local** — no
cloud service, no Adobe account, no browser step, every stage drivable headlessly. Proven
once end to end on the player knight; built to be run again on enemies.

Read `context/animation.md` first — it is the short version of why this is shaped this way.

## Before you start

**Invoke `godot-prompter:animation-system` before touching an AnimationTree**, and
`godot-prompter:assets-pipeline` before import work. Project rule, and it decides node types.

**Do not run the playtest harness unless asked.** Every stage below has a numeric gate for
exactly this reason. Finish, say what you did not verify at runtime, and offer.

Machine-local tool paths come from `.claude/settings.local.json` (gitignored) and are exported
into every session started from the repo root:

```powershell
$env:GODOT_BIN_CONSOLE   # Godot, console build — use this one when you need stdout
$env:BLENDER_BIN         # headless Blender
$env:HUNYUAN3D_PY        # image→mesh venv interpreter    (see the `hunyuan3d` skill)
$env:SKINTOKENS_PY       # mesh→rig venv interpreter      (see the `skintokens` skill)
```

Install layouts, version pins and their failure modes live in the **user-level** `hunyuan3d`
and `skintokens` skills, not here — this repo stays machine-agnostic. Invoke them when a tool
misbehaves rather than debugging from first principles.

Intermediates go in **`local/rigging/work/`** (gitignored). Only the final GLB enters
`assets/models/`. Stage 1 is the exception: the Hunyuan3D scripts are hardcoded to write into
their own install tree.

## The five stages

| # | Stage | Tool | Gate |
|---|---|---|---|
| 1 | image → T-pose mesh | Hunyuan3D-2 | look at the preview render |
| 2 | mesh → rig | SkinTokens | `glb_inspect.py --tree`, judge the skeleton |
| 3 | normalize the rig | `bl_normalize_rig.py` | assertions inside the script |
| 4 | author clips | `bl_author_anims.py` | the printed numbers, then **one** contact sheet |
| 5 | into the game | Godot import + scene | two `verify_*.gd` scripts, both asserted |

Stages 1–2 are gated: each proves the next is worth attempting. Stage 4 is the long pole —
hand-authored keyframes are real work and quality is the limiting factor on the whole chain.

### Keep every intermediate — re-entry is the normal case

Each stage writes a **new file** rather than editing in place, so the chain can be re-entered
anywhere without redoing what came before. Name them so the stage is obvious:

```
<name>_tpose_lowpoly.glb    Stage 1   in the Hunyuan3D install tree
<name>_rigged.glb           Stage 2   local/rigging/work/
<name>_normalized.glb       Stage 3   local/rigging/work/   <-- re-enter here to retune motion
<name>_animated.glb         Stage 4   local/rigging/work/
assets/models/<name>.glb    Stage 5   the repo, with its own .import and UID
```

| What you want | Re-run |
|---|---|
| Tune a pose, retime a clip | 4 → 5. Input is `_normalized.glb`. |
| **Add a clip** to an existing character | 4 → 5, then add the state to the AnimationTree, the clip to `LOOP_MODES` in the asset's import script, and the name to both `verify_*.gd` constant lists. Four places; missing any one fails silently. |
| Move the weapon socket, fix bone rolls | 3 → 5. Stage 4's poses are expressed in world axes, so they mostly survive a re-normalize — but re-read the printed numbers, do not assume. |
| Re-rig (bad skeleton, re-roll sampling) | 2 → 5. |
| Change the mesh at all | 1 → 5. A new mesh means new skin weights means everything downstream. |

Stage 5's GLB always gets a **new filename** in `assets/models/`, never an overwrite of a
tracked one — a fresh `.import` and UID is the point. Delete the superseded asset in the same
pass as the `ext_resource` swap: earlier leaves a broken reference, later leaves dead weight.

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
specific has to move the **elbow**, not just the wrist. This is not a bug to fix.

## Stage 4 — author the clips

```powershell
& $env:BLENDER_BIN -b -P tools/rigging/bl_author_anims.py -- <normalized.glb> <animated.glb>
```

Motion is written **directly onto the rig that will play it**, so there is no retargeting step
at all: no BoneMap, no `SkeletonProfileHumanoid` mapping, no mocap library, no Blender
retarget addon. **All clips are in-place** — translation stays with the entity's velocity
code. No root motion.

**Key every bone in every clip.** The clips then carry identical track sets and the
AnimationTree can blend any pair without a bone snapping to rest.

### The pose vocabulary — this is what makes it tractable

Because Stage 3 guarantees local Z faces front, local X is the flexion axis — but it points a
*different world direction on every bone*. Writing raw local angles needs a fresh sign
convention per bone. So poses are lists of rotations about **world** axes, and `Pose` carries
the accumulated pose down the chain so a named axis is the true world axis regardless of what
the parents are doing. After the 180° turn: **+X = character's right, +Y = front, +Z = up.**

| Op | Meaning |
|---|---|
| `("X"\|"Y"\|"Z", deg)` | true world axis |
| `("twist", deg)` | about the bone's own current direction — wrist roll, axial arm roll |
| `("bend", deg)` | about the bone's own current local X — the normalizer's flexion axis |
| `("loc", (x,y,z))` | world-space offset, written into the bone's local frame |
| `("pivot", (x,y,z))` | shift so the rotation reads as happening about that point |

Ops apply in listed order and compose. Signs, verified in practice: thigh forward =
`UpperLeg` +X; spine forward = `Spine` −X; knee flexion = `LowerLeg` −X; +Y raises the left arm
and lowers the right. Mirror pairs keep the **same** sign about X and reverse about Y and Z —
`swap_sides()` does exactly that.

Rotating a joint about +X moves everything *below* it forward and everything *above* it
backward. Rest is a **T-pose**, so every clip starts from a `STANCE` layer that brings the arms
down; clip poses are deltas layered on top.

### Per character, edit

`STANCE` and the clip constants (`IDLE`, `RUN`, `ATTACK`, `ROLL`), the `CLIPS` registry, and
`SWORD_LENGTH` if the character holds something else. The `Pose` machinery, `swap_sides()`,
`layered()` and the report are generic — leave them alone. Clip names and lengths become the
AnimationTree's state names and the entity's state durations, so pick them together.

### Review: numbers first, one picture second

The script prints, per keyframe, the world position of head, hands and feet plus the direction
and tip of the blade. **That is the cheap half of reviewing an animation** — it catches a foot
through the floor, a sword swinging backwards, or a head under the ground with nothing
rendered. Reference numbers from the knight, for calibration:

- **idle** — head 1.55–1.57, toes 0.04–0.06, blade within 8° of vertical, ~6 cm of drift.
- **run** — planted toe 0.05–0.10 (rest 0.05), swinging toe to 0.42, head bobs 1.50–1.58.
- **attack** — tip travels back over the right shoulder, then down and across to front-left.
- **roll** — head 1.56 → 0.05 → 0.36 → 1.56, minimum ~0.03. Never below the floor.

Only then, for what numbers cannot answer:

```powershell
& $env:BLENDER_BIN -b -P tools/rigging/bl_anim_contact_sheet.py -- `
    <animated.glb> local/rigging/anim_sheet.png 5 150 190
```

**One small sheet, never per-frame captures.** Each screenshot costs ~250 tokens that then
ride along for the whole session. Row order is printed to stdout — it is whatever the NLA
tracks come back in, not the authoring order.

### Two things that look like bugs and are not

- **The roll's last keyframe holds −360°, not 0.** A key at 0 makes the f-curve unwind the
  whole revolution backwards over the final frames. −360 and 0 are the same orientation and
  Godot's slerp handles the quaternion sign when blending out.
- **The contact sheet prints frame ranges that do not match the authored ones.** glTF stores
  keyframe times in *seconds*; the importer converts at the scene's fps, which defaults to 24
  against the 30 these are authored at. Seconds are the number that survives the round trip.

## Stage 5 — into the game

Copy the animated GLB into `assets/models/` under a **new filename** so it gets its own
`.import` and UID, then follow the **`generated-3d-assets`** skill — its "Rigged assets"
section carries the scene wiring, the `AnimationTree` `root_node` rule, the socket path shape,
and the import-script rules. The short version of what must not be got wrong:

- The `AnimationTree`'s `root_node` must resolve to the **instanced model**, not the entity
  root. Wrong, and every bone track fails to resolve silently.
- Anything glTF cannot carry — loop modes, event tracks — goes in a per-asset **import
  script**, never in the `.import` file's `_subresources`.
- Leave `animation/remove_immutable_tracks=false` when clips key every bone.
- Never delete a `.glb.import` to force a reimport; it mints a new UID and orphans every
  `ext_resource`.

### The gates, both asserted

```powershell
& $env:GODOT_BIN_CONSOLE --path . --headless --import
& $env:GODOT_BIN_CONSOLE --path . --headless --script res://tools/rigging/verify_rigged_import.gd
& $env:GODOT_BIN_CONSOLE --path . --headless --script res://tools/rigging/verify_player_scene.gd
& $env:GODOT_BIN_CONSOLE --path . --headless --quit-after 120
```

Both `verify_*.gd` scripts are **written for the knight** — `MODEL`, `EXPECTED_CLIPS`,
`SCENE`, `SOCKET_PATH` and the transition list are constants at the top. Copy and re-point
them for a new character rather than loosening them; the value is entirely in their being
specific. The second one *runs* the attack: it puts the entity in the tree, flips the
AnimationTree to manual process with immediate method callbacks, advances it by hand through
the clip, and asserts the strike actually fired. A method-track path that resolves to the
wrong node reads perfectly well on inspection and deals zero damage in play.

A clean `--quit-after` run proves none of this. White, mis-scaled, mis-rotated, and
zero-damage assets all pass it.

---

## Traps, all paid for once

**Blender**

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

**Everywhere**

- Keep printed strings **ASCII**. The Windows console is cp1252 and mangles em-dashes.
- **Never pipe pip through `tail`/`head`** — the shell reports the pipe's exit status, so a
  failed install reads as success.
- Add a `.gdignore` to any scratch directory inside the project, or Godot reimports every
  contact sheet on each `--headless --import`.

## Where each half is documented

| Half | Lives in | Why |
|---|---|---|
| Install layouts, version pins, VRAM, wheels | user-level `hunyuan3d` + `skintokens` skills | machine-local, absolute paths |
| Stage 3/4 mechanics and Blender traps | `tools/rigging/*.py` docstrings | next to the code they constrain |
| Godot import + scene wiring | `generated-3d-assets` skill | shared with unrigged assets |
| Why the project is shaped this way | `context/animation.md` | project memory, loaded on demand |

## Known rough edges

Honest about what "it worked" meant on the first run through:

- Motion is hand-authored keyframes, and it reads as hand-authored keyframes. That was the
  accepted trade for a fully-local pipeline with no mocap dependency; the contact-sheet loop
  is what keeps iterating on it cheap.
- `LeftFoot`/`RightFoot` normalize with local Y at ≈35° off horizontal, so the ankle's neutral
  is slightly toe-down. Harmless for in-place clips. Revisit only if footplant reads wrong.
- Swinging a straight leg forward lifts the foot fast — 34° of thigh is 13 cm off the ground —
  so run-cycle amplitudes need to be much smaller than they look on paper.
- Most of the Stage 4 tuning time went into the sword arm, because of the perpendicular grip.
  Budget for that on any character holding something.
