# Combat

Damage runs through three composable nodes in `systems/components/`: a **Hitbox** deals it,
a **Hurtbox** receives it, a **Health** node stores it. An entity gets combat by adding the
nodes it needs — nothing subclasses anything.

**Flow** — `attack` → cooldown check → swing tween → `attack_impact_delay` elapses →
`Hitbox.strike()` → each overlapping Hurtbox → `Health.take_damage()` → `health_changed` /
`died` → the owning entity reacts and rebroadcasts on `EventBus`.

**Layers** — `1 world` (floor, trunks), `2 player` (body), `3 choppable` (hurtboxes),
`4 player_hitbox` (the swing volume). Named in `project.godot`.

**Decisions**
- The hitbox is **strike-triggered, not `area_entered`-triggered** — standing next to a
  target must never damage it. It tracks overlaps continuously so `strike()` lands on the
  frame it is called, instead of waiting a physics tick for `monitoring` to warm up.
- Damage lands mid-swing (`attack_impact_delay`), not on the button press, so the hit reads.
- Hurtboxes have an empty collision mask: they detect nothing, they exist to be found.

**Gotchas**
- Drive **feedback** off `hurt` but **state broadcasts** off `health_changed` — `hurt` fires
  *before* damage is applied, so it still reports the pre-hit total.
- Wire `hurtbox.health_component` from the owner's `_ready()`; see [conventions](conventions.md).

_Files: systems/components/*.gd, entities/player/player.gd_
