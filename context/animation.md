# Animation

The knight is rigged — 36 humanoid bones, five in-place clips (`idle`, `run`, `attack`,
`roll`, `jump`) authored as scripted keyframes by `tools/rigging/bl_author_anims.py`.

**Decisions**
- Motion is **authored directly on the rig**, so retargeting is off the critical path: no
  BoneMap, no `SkeletonProfileHumanoid`, no mocap library. Bones carry humanoid names anyway,
  so external clips stay possible without anything depending on it.
- Clips are **in-place**; translation stays with `player.gd`'s velocity code. No root motion.
- Gameplay state is the enum in `player.gd`; the `AnimationTree` runs a *separate* state
  machine that is only ever told what to show. Damage lands from a Call Method track on the
  `attack` clip, not a timer — see [combat](combat.md).

**Gotchas**
- The `AnimationTree`'s `root_node` must resolve to the **instanced model**, not to `Player`.
  Point it at `Player` and all 108 bone tracks fail to resolve — the knight stands in its
  T-pose rest, no error printed.
- glTF carries neither loop modes nor event tracks, so both are applied by
  `tools/import/knight_rigged_import.gd`. An unwired `import_script/path` loses both silently,
  and the swing then deals zero damage.
- Keep `animation/remove_immutable_tracks=false`. Some bones hold a constant *non-rest* value
  for a whole clip (the right wrist's roll through `run`); dropped as "immutable", the wrist
  snaps to T-pose rest and the sword points wrong for the entire cycle.
- The sword's grip is the `WeaponSocket` empty alone, and Blender exports its rotation wrong
  — see [conventions](conventions.md). `verify_rigged_import.gd` asserts it: at rest the
  socket is world-axis aligned, blade up its +Y. Never correct it in `player.tscn`.
- `bl_normalize_rig.py` bakes the 180° Blender→Godot turn into the mesh and rest bones. Never
  add a correction transform in the scene, or the two cancel and the knight moonwalks.
- Assert, don't eyeball: `tools/rigging/verify_rigged_import.gd` covers the asset,
  `verify_player_scene.gd` the seam — it runs the swing and checks the strike lands.

_Files: tools/rigging/*, tools/import/knight_rigged_import.gd, entities/player/player.tscn_
