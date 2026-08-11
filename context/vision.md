# Vision

A 3D knight prototype: third-person melee against a fixed, Warcraft 3-style overhead
camera, currently proving out one loop — walk up to a thing, swing at it, watch it break.

**Decisions**
- The tree, the knight, and its sword are generated low-poly models (image-to-3D, then
  decimated); anything not yet replaced is still greybox primitives. They remain art
  placeholders — flat-shaded, deliberately cheap — so feel is tuned without waiting on a
  real art pipeline.
- The **player is rigged and animated** off a fully local pipeline (see
  [animation](animation.md)); everything else is still unrigged. Feedback for those still
  reads through emission flash, squash, and tween-driven motion.
- `dodge` is **committed** — it rolls, with its own state, clip, and cooldown. That was a
  scope decision taken alongside the animation work, not a side effect of it.
- Systems are built as reusable components (`systems/components/`) from the start, so the
  first target being a tree rather than an enemy costs nothing later.

**Open — confirm with the user before assuming**
- Genre and scope past the chop loop: is resource gathering the point, or is the tree just
  a convenient punching bag on the way to combat?
- Whether the fixed RTS camera is the shipping camera or scaffolding.
- `block`, `jump`, and `interact` are bound in the Input Map but nothing reads them yet —
  bound as intent, not as a commitment.

_Files: entities/player/player.gd, entities/tree/tree.gd_
