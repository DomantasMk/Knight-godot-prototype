# Camera and movement

One coupled system: `RtsCamera` is a fixed-angle Warcraft 3-style follow camera, and the
player's WASD is interpreted **in the camera's frame**, so the camera's yaw defines what
"forward" means. Changing one changes the other.

**Decisions**
- Numbers are derived from Warcraft 3's game camera (distance 1650, angle of attack 304,
  rotation 90 → 56° below horizontal, axis-aligned). WC3 is perspective, not orthographic —
  the isometric feel comes from the fixed steep angle. Distance is pulled in from a faithful
  ~26 m to 18 m, because at 26 m a 1.8 m capsule is unreadably small.
- The player has **no camera control at all** — no orbit, no zoom, no roll. Deliberate.
- Space hops 0.8 m under **1.8× gravity**, 0.6 s of air. Real gravity floats any readable
  height; the 56° camera foreshortens the rise by half anyway. No coyote time, no jump
  buffer, no variable height — the floor is flat, and cutting the rise desyncs the clip.
- The camera sets its rotation directly instead of `look_at()`: framing stays rock steady
  while the position smooths, with no wobble as the target moves.

**Gotchas**
- **The camera must be a sibling of the player, never a child.** The knight rotates to face
  his travel direction and would drag a child camera around with him.
- A level that assigns `target` must then call `snap_to_target()` — see [level-01](level-01.md).
- The `jump` clip's length *is* that airtime, so the landing pose arrives with the feet.
  Retune `jump_height` or `gravity_scale` and retime the clip too — `_check_jump_clip()`
  warns in debug builds once the two drift apart.
- `Input.get_vector()` reports `y = -1` for `move_forward`, hence the negation in
  `_movement_direction()`. Both camera basis vectors are flattened onto the ground plane
  before use, and only `velocity.x/z` are steered so gravity on `velocity.y` survives.

_Files: systems/rts_camera.gd, entities/player/player.gd_
