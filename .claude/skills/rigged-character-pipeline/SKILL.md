---
name: rigged-character-pipeline
description: Use when taking a character from nothing to a rigged, animated, playable entity in KnightPrototype — generating or rigging a humanoid mesh, predicting a skeleton, normalizing bone names and rolls, authoring animation clips in Blender, and wiring the result into a Godot scene with an AnimationTree. Covers the five-stage local pipeline, what to delegate, and the traps each stage hides. Triggers on "rig this model", "animate a character", "new enemy/character asset", "add animations to", "model to rig to animation".
---

# The rigged-character pipeline

Takes a humanoid mesh to a rigged, animated entity in this project. **Fully local** — no
cloud service, no Adobe account, no browser step, every stage drivable headlessly. Proven
once end to end on the player knight; built to be run again on enemies.

Read `context/animation.md` first — it is the short version of why this is shaped this way.

**You are the orchestrator.** Stages 1–4 run in subagents; you run Stage 5. Read only this
file and `stages/godot.md`. Do **not** read `stages/mesh-and-rig.md`, `stages/clips.md`, or
`stages/traps.md` — those are for the agents, and pulling them in here is the exact cost this
structure exists to avoid.

## Why this is delegated — the measured reason

A full run is **~170 requests**, each adding ~1k tokens to context. Nothing is individually
large; the biggest single tool result ever recorded was 6.4k. But three of the first five
pipeline sessions hit **225k, 243k and 246k** against a 200k limit, and the fixed baseline
(system + tools + CLAUDE.md) is already 38–43k before any work starts.

The grind is the cost: Stage 1's regenerate-and-look loop and Stage 4's tune-run-read loop are
each 40–80 requests of small calls whose *intermediate* detail you never need — only the
verdict. A subagent absorbs the whole loop into its own 200k window and hands back a
twenty-line report. Break-even is about three requests, so every loop below clears it easily.

**Budget check:** you should finish a whole character at **~80–90k**. If you are past 120k as
the orchestrator, you have absorbed work that belonged in an agent — stop and delegate the
rest rather than pushing on.

Two rules that follow, and are not negotiable:

- **Never inline a stage to "just check something quickly."** One quick check is how a 40k
  loop lands in your window. Re-spawn the agent with a narrower brief instead.
- **Never write a HANDOFF.md.** Handoff docs were how earlier runs fought the limit, and they
  cost ~25k of context to produce — more than the delegation they were substituting for. The
  agent reports below *are* the handoff.

## Before you start

**Invoke `godot-prompter:animation-system` before touching an AnimationTree**, and
`godot-prompter:assets-pipeline` before import work. Project rule, and it decides node types.
This applies to the subagents too — their definitions say so, but they do not inherit it from
you, so a hand-written brief must repeat it.

**Do not run the playtest harness unless asked.** Every stage has a numeric gate for exactly
this reason. Finish, say what you did not verify at runtime, and offer.

Machine-local tool paths come from `.claude/settings.local.json` (gitignored) and are exported
into every session started from the repo root — subagents inherit them:

```powershell
$env:GODOT_BIN_CONSOLE   # Godot, console build — use this one when you need stdout
$env:BLENDER_BIN         # headless Blender
$env:HUNYUAN3D_PY        # image->mesh venv interpreter    (see the `hunyuan3d` skill)
$env:SKINTOKENS_PY       # mesh->rig venv interpreter      (see the `skintokens` skill)
```

Install layouts, version pins and their failure modes live in the **user-level** `hunyuan3d`
and `skintokens` skills, not here — this repo stays machine-agnostic.

Intermediates go in **`local/rigging/work/`** (gitignored). Only the final GLB enters
`assets/models/`. Stage 1 is the exception: the Hunyuan3D scripts are hardcoded to write into
their own install tree.

## The five stages

| # | Stage | Tool | Runs in | Gate |
|---|---|---|---|---|
| 1 | image → T-pose mesh | Hunyuan3D-2 | `character-mesh-rig` | look at the preview render |
| 2 | mesh → rig | SkinTokens | `character-mesh-rig` | `glb_inspect.py --tree`, judge the skeleton |
| 3 | normalize the rig | `bl_normalize_rig.py` | `character-mesh-rig` | assertions inside the script |
| 4 | author clips | `bl_author_anims.py` | `character-clip-author` | printed numbers, then **one** contact sheet |
| 5 | into the game | Godot import + scene | **you** | two `verify_*.gd` scripts, both asserted |

Stages 1–2 are gated: each proves the next is worth attempting. Stage 4 is the long pole —
hand-authored keyframes are real work and quality is the limiting factor on the whole chain.

Stage 5 stays with you deliberately. It edits tracked repo files, needs the project's scene
and import conventions, and is the part the user reviews. Delegating tracked-file edits to a
cold agent is where this decomposition would go wrong.

## Delegating: the two briefs

Spawn with `Agent`, `subagent_type` as named. Both write only into `local/rigging/work/` and
neither touches tracked files, so they are safe to run in the working directory.

### `character-mesh-rig` — Stages 1–3

**Give it:** character name (used for every filename); the reference image path, or the brief
to build one; triangle budget (~6–8k for a player-facing character, far less for scenery);
which hand carries a weapon and roughly how it should sit.

**It returns (~20 lines):** the path to `<name>_normalized.glb`; bone count and the humanoid
names assigned; the socket's bone and rest position; the `glb_inspect --require` result; and
any place it had to deviate from the stage doc.

### `character-clip-author` — Stage 4

**Give it:** the path to `<name>_normalized.glb`; the clip names *and durations*; the
character's height and weapon length so it can calibrate the gate numbers.

**It returns (~25 lines):** the path to `<name>_animated.glb`; the per-clip gate table
(head / toe / blade extremes); the clip names and lengths **in seconds as exported**; and any
deviation.

Clip names and lengths become the AnimationTree's state names and the entity's state
durations — so decide them *before* you spawn, and pass them in. Renaming afterwards means
re-running Stage 4.

### Reading the report

The report is the whole interface. If it does not answer a question you need for Stage 5,
`SendMessage` the same agent — its context is still warm and it still has the numbers. Do
**not** re-derive the answer yourself by opening the intermediates; that is the inlining
mistake in a different costume.

## Keep every intermediate — re-entry is the normal case

Each stage writes a **new file** rather than editing in place, so the chain can be re-entered
anywhere without redoing what came before. Name them so the stage is obvious:

```
<name>_tpose_lowpoly.glb    Stage 1   in the Hunyuan3D install tree
<name>_rigged.glb           Stage 2   local/rigging/work/
<name>_normalized.glb       Stage 3   local/rigging/work/   <-- re-enter here to retune motion
<name>_animated.glb         Stage 4   local/rigging/work/
assets/models/<name>.glb    Stage 5   the repo, with its own .import and UID
```

**Do not delete `local/rigging/work/` when a character ships.** The knight's intermediates were
cleaned up, and that made every downstream change — retuning a clip, adding one, or even
verifying a refactor of the authoring script — a full re-run from Stage 1. Keeping them is
free; the directory is gitignored.

| What you want | Re-run | Delegate to |
|---|---|---|
| Tune a pose, retime a clip | 4 → 5. Input is `_normalized.glb`. | `character-clip-author` |
| **Add a clip** to an existing character | 4 → 5, then add the state to the AnimationTree, the clip to `LOOP_MODES` in the asset's import script, and the name to both `verify_*.gd` constant lists. Four places; missing any one fails silently. | `character-clip-author`, then you |
| Move the weapon socket, fix bone rolls | 3 → 5. Stage 4's poses are expressed in world axes, so they mostly survive a re-normalize — but re-read the printed numbers, do not assume. | `character-mesh-rig`, then `character-clip-author` |
| Re-rig (bad skeleton, re-roll sampling) | 2 → 5. | both |
| Change the mesh at all | 1 → 5. A new mesh means new skin weights means everything downstream. | both |

Stage 5's GLB always gets a **new filename** in `assets/models/`, never an overwrite of a
tracked one — a fresh `.import` and UID is the point. Delete the superseded asset in the same
pass as the `ext_resource` swap: earlier leaves a broken reference, later leaves dead weight.

## Stage 5 — into the game

This one is yours; the detail is in **`stages/godot.md`**. Read that when you get here, not
before. The short version of what must not be got wrong:

- The `AnimationTree`'s `root_node` must resolve to the **instanced model**, not the entity
  root. Wrong, and every bone track fails to resolve silently.
- Anything glTF cannot carry — loop modes, event tracks — goes in a per-asset **import
  script**, never in the `.import` file's `_subresources`.
- Leave `animation/remove_immutable_tracks=false` when clips key every bone.
- Never delete a `.glb.import` to force a reimport; it mints a new UID and orphans every
  `ext_resource`.

## Where each half is documented

| Half | Lives in | Why |
|---|---|---|
| Orchestration, budget, delegation | this file | the only thing the main thread loads |
| Stages 1–3 mechanics | `stages/mesh-and-rig.md` | loaded by `character-mesh-rig` only |
| Stage 4 pose vocabulary and review | `stages/clips.md` | loaded by `character-clip-author` only |
| Blender traps, rough edges | `stages/traps.md` | loaded by both agents |
| Deeper Stage 3/4 mechanics | `tools/rigging/*.py` docstrings | next to the code they constrain |
| Stage 5 import + scene wiring | `stages/godot.md` + `generated-3d-assets` skill | shared with unrigged assets |
| Install layouts, version pins, VRAM | user-level `hunyuan3d` + `skintokens` skills | machine-local, absolute paths |
| Why the project is shaped this way | `context/animation.md` | project memory, loaded on demand |

## Known cheap win, not yet taken

`bl_author_anims.py` mixes generic machinery (`Pose`, `swap_sides()`, `layered()`, the report)
with per-character constants (`STANCE`, the clip poses, `CLIPS`, `SWORD_LENGTH`). The Stage 4
loop therefore edits a 463-line file to change a number, and each edit rides in the agent's
context. Splitting the constants into a small per-character spec module the script imports
would shrink that loop several-fold, as would having the script assert its gate ranges and
exit non-zero rather than printing numbers for a human to judge.

Not done, because the knight's `_normalized.glb` no longer exists, so the refactor could not
be verified against known-good output. **Do it at the start of the next character run**, while
a fresh `_normalized.glb` is on disk and re-running the script proves the split changed
nothing.
