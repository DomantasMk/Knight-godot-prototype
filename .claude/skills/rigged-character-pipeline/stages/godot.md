# Stage 5 — into the game

The orchestrator runs this, not an agent: it edits tracked repo files, needs the project's
scene and import conventions, and is the part the user reviews.

**Invoke `godot-prompter:animation-system` before touching the AnimationTree** and
`godot-prompter:assets-pipeline` before the import work. Project rule.

Your inputs are the two agent reports: the path to `<name>_animated.glb`, the clip names and
their lengths in seconds, which clips loop, and where the attack's impact falls.

## Wiring

Copy the animated GLB into `assets/models/` under a **new filename** so it gets its own
`.import` and UID, then follow the **`generated-3d-assets`** skill — its "Rigged assets"
section carries the scene wiring, the `AnimationTree` `root_node` rule, the socket path shape,
and the import-script rules. The short version of what must not be got wrong:

- The `AnimationTree`'s `root_node` must resolve to the **instanced model**, not the entity
  root. Wrong, and every bone track fails to resolve silently — the character stands in its
  T-pose rest with no error printed.
- Anything glTF cannot carry — loop modes, event tracks — goes in a per-asset **import
  script**, never in the `.import` file's `_subresources`. An unwired `import_script/path`
  loses both silently, and the swing then deals zero damage.
- Leave `animation/remove_immutable_tracks=false` when clips key every bone. Some bones hold a
  constant *non-rest* value for a whole clip; dropped as "immutable", they snap to T-pose rest
  for the entire cycle.
- Never delete a `.glb.import` to force a reimport; it mints a new UID and orphans every
  `ext_resource`.
- Never add a rotation correction in the scene. `bl_normalize_rig.py` already baked the 180°
  Blender→Godot turn into the mesh and rest bones; the two cancel and the character moonwalks.

Delete the superseded asset in the same pass as the `ext_resource` swap — earlier leaves a
broken reference, later leaves dead weight.

## The gates, both asserted

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

## Adding one clip to a character that already shipped

Four places, and missing any one fails silently:

1. the new state in the AnimationTree, plus its transitions
2. the clip in `LOOP_MODES` in that asset's import script
3. the name in `verify_rigged_import.gd`'s `EXPECTED_CLIPS`
4. the name in `verify_player_scene.gd`'s transition list

## Finally

Update `context/animation.md` in the same commit if anything there is now wrong — a stale note
is worse than no note. State plainly what you did **not** verify at runtime, and offer to
playtest rather than running it unasked.
