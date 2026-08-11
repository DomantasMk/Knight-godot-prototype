# Stage 4 — author the clips

You are the `character-clip-author` agent. Your input is
`local/rigging/work/<name>_normalized.glb`; your output is `<name>_animated.glb` plus a short
report. Read `stages/traps.md` before running Blender.

Write **only** into `local/rigging/work/`. Never touch a tracked repo file. Keep the
intermediates when you finish.

```powershell
& $env:BLENDER_BIN -b -P tools/rigging/bl_author_anims.py -- <normalized.glb> <animated.glb>
```

Motion is written **directly onto the rig that will play it**, so there is no retargeting step
at all: no BoneMap, no `SkeletonProfileHumanoid` mapping, no mocap library, no Blender
retarget addon. **All clips are in-place** — translation stays with the entity's velocity
code. No root motion.

**Key every bone in every clip.** The clips then carry identical track sets and the
AnimationTree can blend any pair without a bone snapping to rest.

This is the long pole of the whole pipeline, and quality here is the limiting factor on the
result. Budget your context accordingly — see "Running the loop cheaply" below.

## The pose vocabulary — this is what makes it tractable

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

**The grip is perpendicular to the forearm** — a blade cannot point up while the arm hangs
down, because it is confined to the plane perpendicular to the forearm. A pose wanting the
blade somewhere specific has to move the **elbow**, not just the wrist. Most of the knight's
Stage 4 time went here; budget for it on any character holding something.

## Per character, edit

`STANCE` and the clip constants (`IDLE`, `RUN`, `ATTACK`, `ROLL`), the `CLIPS` registry, and
`SWORD_LENGTH` if the character holds something else. The `Pose` machinery, `swap_sides()`,
`layered()` and the report are generic — leave them alone.

Clip names and durations come **from the orchestrator's brief**, because they become the
AnimationTree's state names and the entity's state durations. Do not invent or rename them; if
a duration cannot work, say so in the report rather than silently changing it.

## Review: numbers first, one picture second

The script prints, per keyframe, the world position of head, hands and feet plus the direction
and tip of the blade. **That is the cheap half of reviewing an animation** — it catches a foot
through the floor, a sword swinging backwards, or a head under the ground with nothing
rendered. Reference numbers from the knight (1.57 m tall), for calibration — scale them to the
character height you were given:

- **idle** — head 1.55–1.57, toes 0.04–0.06, blade within 8° of vertical, ~6 cm of drift.
- **run** — planted toe 0.05–0.10 (rest 0.05), swinging toe to 0.42, head bobs 1.50–1.58.
- **attack** — tip travels back over the right shoulder, then down and across to front-left.
- **roll** — head 1.56 → 0.05 → 0.36 → 1.56, minimum ~0.03. Never below the floor.

Only then, for what numbers cannot answer:

```powershell
& $env:BLENDER_BIN -b -P tools/rigging/bl_anim_contact_sheet.py -- `
    <animated.glb> local/rigging/anim_sheet.png 5 150 190
```

**One small sheet, near the end, never per-frame captures.** Each screenshot costs 250–1000
tokens that then ride along for the rest of your window. Row order is printed to stdout — it is
whatever the NLA tracks come back in, not the authoring order.

## Running the loop cheaply

This loop is what blew the 200k limit on earlier runs, from inside the main thread. You have
your own window now, but it is not unlimited:

- **Edit, do not rewrite.** `bl_author_anims.py` is 463 lines; a `Write` of the whole file
  costs ~5k every time. Use `Edit` on the constant you are changing.
- **Do not re-read the script** between iterations to check what you changed — you already
  know, and the harness would have errored if the edit failed.
- **Batch your changes.** Adjust every number you already believe is wrong, then run once.
  Run-per-number is the expensive habit.
- **Read the printed numbers, not the file.** The gates are numeric on purpose.
- If you approach ~150k, write your current constants into
  `local/rigging/work/<name>_clip_notes.md` — that one file is a legitimate handoff for a
  re-spawn, unlike the sprawling HANDOFF.md this pipeline used to grow.

## Two things that look like bugs and are not

- **The roll's last keyframe holds −360°, not 0.** A key at 0 makes the f-curve unwind the
  whole revolution backwards over the final frames. −360 and 0 are the same orientation and
  Godot's slerp handles the quaternion sign when blending out.
- **The contact sheet prints frame ranges that do not match the authored ones.** glTF stores
  keyframe times in *seconds*; the importer converts at the scene's fps, which defaults to 24
  against the 30 these are authored at. Seconds are the number that survives the round trip.

---

## What to report back

Twenty-five lines, no more. The orchestrator wires Stage 5 off this:

- the path to `<name>_animated.glb`, and that intermediates are still on disk
- the clip names and their lengths **in seconds as exported** — Stage 5's import script,
  AnimationTree states and both `verify_*.gd` constant lists are keyed off these
- the gate table: per clip, the head / toe / blade extremes you actually measured
- which clips loop and which do not — the import script needs it
- for the attack clip, **where in the clip the impact falls**, in seconds
- any duration you could not honour, and what you did instead

Do not paste the full per-keyframe dump, the Blender log, or the constants you settled on. If
the orchestrator needs one, it will message you while your context is still warm.
