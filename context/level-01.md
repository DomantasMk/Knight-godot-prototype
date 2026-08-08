# level_01

The demo scene, and the project's main scene — a greybox field that exists so F5 always
shows the current state of the loop. It is a test harness, not a designed level: rearrange
or replace it freely.

**Contents** — 40×40 floor with its top surface at `y = 0`, a 6 m dirt road running along
Z through `x = 0`, directional light + procedural sky, the player at `(0, 0.1, 8)`, an
`RtsCamera` sibling, `DemoHud`, and an empty `Trees` parent filled at runtime.

**Decisions**
- Trees are scattered in `_ready()` rather than placed in the `.tscn` — keeps the scene
  file small and free of hand-written transforms that are easy to get wrong.
- The scatter is seeded (`scatter_seed = 1337`), so the layout is byte-identical every run
  and a visual change is never confused with a reroll. Change the seed to reroll.
- Scatter rejects candidates over the road, near spawn, or too close to another trunk;
  it retries rather than relaxing the constraints, so it can place fewer than
  `tree_count` trees. That is fine for a demo.

**Gotchas**
- The level's `_ready()` runs *after* its children's, which is why it assigns
  `_camera.target` and then calls `snap_to_target()` — drop the snap and the camera visibly
  slides in from the world origin on the first frames.
- Tree scale is randomized uniformly on purpose; see [conventions](conventions.md) on Jolt.

_Files: levels/level_01/level_01.gd, levels/level_01/level_01.tscn_
