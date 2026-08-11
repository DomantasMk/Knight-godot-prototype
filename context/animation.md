# Animation

The knight is rigged — 36 humanoid bones, five in-place clips (`idle`, `run`, `attack`,
`roll`, `jump`). The clips are **authored in a different repo**,
[3d-asset-preparation-ai-pipeline](https://github.com/DomantasMk/3d-asset-preparation-ai-pipeline),
and arrive here as `assets/models/knight_rigged_v2.glb`. Changing how the knight *moves* is a
session over there; everything below is this side of the seam.

**Decisions**
- Motion is **authored directly on the rig**, so retargeting is off the critical path: no
  BoneMap, no `SkeletonProfileHumanoid`, no mocap library. Bones carry humanoid names anyway,
  so external clips stay possible without anything depending on it.
- Clips are **in-place**; translation stays with `player.gd`'s velocity code. No root motion.
- Gameplay state is the enum in `player.gd`; the `AnimationTree` runs a *separate* state
  machine that is only ever told what to show. Damage lands from a Call Method track on the
  `attack` clip, not a timer — see [combat](combat.md).
- The swing is timed against **measured blade speed**, not poses. The strike fires on the
  clip's fastest frame rather than the frame the contact pose was authored on — the eye reads
  contact where motion peaks, and the first version of this clip hit at 42 % of peak and read
  as floaty. `ATTACK_IMPACT_TIME` is that measurement; re-measure it in the pipeline repo
  before moving it, never by eye.
- `attack` ends on an open guard, not back at stance, and `player.gd`'s `attack_lock` releases
  input before the clip ends: the state machine's 0.15 s crossfade finishes the recovery, so
  animating it in the clip would animate it twice and cost responsiveness for nothing.

**Gotchas**
- The `AnimationTree`'s `root_node` must resolve to the **instanced model**, not to `Player`.
  Point it at `Player` and all 108 bone tracks fail to resolve — the knight stands in its
  T-pose rest, no error printed.
- glTF carries neither loop modes nor event tracks, so both are applied by
  `tools/import/knight_rigged_import.gd`. An unwired `import_script/path` loses both silently,
  and the swing then deals zero damage. **Editing that script does not trigger a reimport** —
  Godot keys those off the source file, so the constant changes and nothing happens. Delete the
  cached `.godot/imported/knight_rigged_v2.glb-*.scn` and re-import; never delete the
  `.glb.import`, which mints a new UID and orphans every `ext_resource`.
- Keep `animation/remove_immutable_tracks=false`. Some bones hold a constant *non-rest* value
  for a whole clip (the right wrist's roll through `run`); dropped as "immutable", the wrist
  snaps to T-pose rest and the sword points wrong for the entire cycle.
- The sword's grip is the `WeaponSocket` empty alone, and its rotation is repaired on export —
  see [conventions](conventions.md). `verify_rigged_import.gd` asserts it: at rest the socket
  is world-axis aligned, blade up its +Y. Never correct it in `player.tscn`.
- The 180° Blender→Godot turn is baked into the mesh and the rest bones. Never add a correction
  transform in the scene, or the two cancel and the knight moonwalks.
- Assert, don't eyeball: `verify_rigged_import.gd` covers the asset and `verify_player_scene.gd`
  the seam. The swing's *spacing* — which pose numbers cannot see — is gated on the GLB in the
  pipeline repo, before it ever gets here.

_Files: assets/models/knight_rigged_v2.glb, tools/import/knight_rigged_import.gd, tools/verify/*,
entities/player/player.tscn_
