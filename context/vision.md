# Vision

A 3D knight prototype: third-person melee against a fixed, Warcraft 3-style overhead
camera, currently proving out one loop — walk up to a thing, swing at it, watch it break.

**Decisions**
- The tree, the knight, and its sword are generated low-poly models (image-to-3D, then
  decimated); anything not yet replaced is still greybox primitives. The models are art
  placeholders in the same spirit as the greybox — flat-shaded, unrigged, no animation —
  so feel is still tuned without waiting on a real art pipeline.
- Feedback over fidelity: hits read through emission flash, squash, and tween-driven
  motion rather than animation clips. There is no `AnimationPlayer` in the project yet.
- Systems are built as reusable components (`systems/components/`) from the start, so the
  first target being a tree rather than an enemy costs nothing later.

**Open — confirm with the user before assuming**
- Genre and scope past the chop loop: is resource gathering the point, or is the tree just
  a convenient punching bag on the way to combat?
- Whether the fixed RTS camera is the shipping camera or scaffolding.
- `block`, `dodge`, `jump`, and `interact` are bound in the Input Map but nothing reads
  them yet — bound as intent, not as a commitment.

_Files: entities/player/player.gd, entities/tree/tree.gd_
