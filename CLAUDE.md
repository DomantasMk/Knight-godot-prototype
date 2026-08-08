# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`KnightPrototype` — an early-stage **3D** Godot 4.7 game prototype. One gameplay loop is playable in greybox: a knight walks under a fixed overhead camera and swings at choppable trees. There is no test suite and no build tooling beyond Godot itself.

Remote: https://github.com/DomantasMk/Knight-godot-prototype (branch `main`).

## Project context

`context/` holds short notes on **why** this project is shaped the way it is — decisions,
intent, and invariants that the code cannot state on its own. The index below is the memory;
each file is the footnote you open only when working in that area.

| Note | |
|---|---|
| [vision](context/vision.md) | 3D knight, fixed WC3-style camera, greybox melee; proving one loop — approach, swing, break. Genre past that is **unconfirmed**. |
| [level-01](context/level-01.md) | The main scene is a **demo harness**, not a designed level: 40×40 floor, road, player at `(0,0.1,8)`, 26 trees scattered at runtime from a fixed seed. Replace freely. |
| [combat](context/combat.md) | Damage = Hitbox (deals, on `strike()` only) → Hurtbox (receives) → Health (stores), composed per entity. Includes the 3D physics layer table. |
| [camera-and-movement](context/camera-and-movement.md) | Fixed 56° follow camera, no player control; WASD is camera-relative, so the two are one system. Camera must be a **sibling** of the player. |
| [conventions](context/conventions.md) | Recurring rules: hand-written `.tscn` `@export` caveat, Jolt uniform-scale rule, `1-exp(-k·dt)` smoothing, tween kill-before-restart, material duplication. |

**Read** a note before changing that area — the gotchas are there because each one cost a bug.
**Update** it in the same commit that invalidates it; a stale note is worse than no note.
Adding or deleting a note means adding or deleting its row above. Full rules and the
template: `context/README.md`. Keep notes under ~25 lines — the cap is what keeps this cheap.

This is project memory, checked in and shared. Preferences about *how the user likes to
work* are not project facts and do not belong here.

## GodotPrompter

This project uses the GodotPrompter plugin. **Before implementing any Godot system, invoke the matching `godot-prompter:*` skill.** This applies to subagents writing Godot code too — you do not receive the plugin's instructions automatically, this file is your only notice of them.

Match the task to a skill, e.g.:

| Building… | Invoke |
|---|---|
| Movement, input, cameras | `player-controller`, `input-handling`, `camera-system` |
| Architecture | `state-machine`, `event-bus`, `scene-organization`, `component-system`, `resource-pattern` |
| Gameplay systems | `inventory-system`, `dialogue-system`, `ability-system`, `save-load` |
| Enemy AI | `ai-navigation` |
| UI, HUD | `godot-ui`, `hud-system`, `responsive-ui` |
| Animation, tweens, audio | `animation-system`, `tween-animation`, `audio-system` |
| Physics, 3D | `physics-system`, `3d-essentials` |
| Shaders, VFX | `shader-basics`, `particles-vfx` |
| GDScript idioms | `gdscript-patterns`, `gdscript-advanced` |
| Test, debug, profile, review | `godot-testing`, `godot-debugging`, `godot-optimization`, `godot-code-review` |

Invoke `godot-prompter:using-godot-prompter` for the full index.

Knowing the engine class is not the same as knowing the pattern — invoke the skill even when the change looks like a one-liner, because a one-liner still picks node types and sets architecture. Having loaded one Godot skill does not cover a different system.

## Directory layout

Co-located feature folders — a feature's scene, script, and helpers live together, so a feature can be moved or deleted as one directory. `assets/` is the exception and stays sorted by type.

```
assets/{audio/{music,sfx},fonts,models,textures}/   raw art and audio
autoloads/                                          singletons (see below)
context/                                            project memory (see above) — .md only, no code
entities/{player,tree,…}/                           <name>.tscn + <name>.gd together
levels/{level_01,main_menu}/                        one folder per level
systems/                                            cross-cutting logic with no scene of its own
systems/components/                                 reusable nodes an entity composes in
resources/                                          .tres data: stats, items, themes
ui/                                                 HUD, menus
```

Empty directories hold a `.gitkeep`; delete it once real files land. If this layout is outgrown (multiple people working art vs. code), the migration target is the split `assets/ scenes/ scripts/` layout — but don't do it preemptively.

## Autoloads

Registered in `project.godot` under `[autoload]`. Keep them few and small; when a rule outgrows a few lines, move it to a plain class in `systems/` and call it from the autoload.

- **`EventBus`** (`autoloads/event_bus.gd`) — signal declarations only, no logic. Cross-system communication goes through here so emitters and listeners need no reference to each other. Add new cross-system signals to this file rather than wiring nodes directly.
- **`GameManager`** (`autoloads/game_manager.gd`) — scene changes, pause state, and the `pause` input action. It sets `PROCESS_MODE_ALWAYS` in `_ready()`; this is load-bearing, since a node on the default process mode is frozen by `get_tree().paused` and could never unpause the game.

## Input

All input goes through Input Map actions — **never hard-code keycodes**. Defined actions:

`move_forward` `move_back` `move_left` `move_right` `jump` `attack` `block` `dodge` `interact` `pause`

Each has a keyboard/mouse binding and a gamepad binding. Movement keys use `physical_keycode` so WASD stays positionally correct on non-QWERTY layouts. Read them with `Input.get_vector()` / `Input.is_action_just_pressed()`.

## Project configuration (`project.godot`)

These settings are already chosen and shape how new code should be written:

- **Renderer**: Forward+, with the Direct3D 12 rendering driver on Windows (`rendering_device/driver.windows="d3d12"`).
- **3D physics**: Jolt Physics (not the legacy Godot Physics). Behavior of joints, damping, and layer masks differs from the default engine — check Jolt-specific docs when tuning.
- **Stretch**: `canvas_items` mode with `expand` aspect, i.e. resolution-independent 2D/UI that gains screen area rather than letterboxing on wider displays.
- **Main scene**: `res://levels/level_01/level_01.tscn` — a greybox demo harness, not a designed level. See [context/level-01.md](context/level-01.md).
- **3D physics layers**: `1 world`, `2 player`, `3 choppable`, `4 player_hitbox`. Named in `[layer_names]`; see [context/combat.md](context/combat.md) for what masks what.

## Commands

Godot is not on `PATH`. The binary paths are machine-specific, so they live in
`.claude/settings.local.json` (gitignored) as `GODOT_BIN` and `GODOT_BIN_CONSOLE` rather
than in this file — that keeps the repo machine-agnostic. Claude Code exports them into
every session it spawns; set them yourself for a shell you opened by hand.

```powershell
$godot = $env:GODOT_BIN                            # e.g. ...\Godot_v4.7.1-stable_win64.exe

& $godot --path .                                  # open in the editor
& $godot --path . res://path/to/scene.tscn         # run one scene
& $godot --path . --headless --import              # reimport / regenerate .godot
& $godot --path . --headless --quit-after 60       # smoke-test: run 60 frames, print errors
```

Use `$env:GODOT_BIN_CONSOLE` instead when you need stdout/stderr captured on the command line — the plain `.exe` detaches from the console on Windows. The last two commands are the cheapest way to verify a change did not break scene loading or parsing.

**These variables are only populated in a session started from the repo root.** Claude Code
reads `.claude/settings.local.json` relative to the session root, so a session opened in a
parent directory gets neither the variables nor this file. Start Claude Code here.

## Notes

- `.godot/` is generated (imports, shader cache, UID cache) and gitignored — never edit it, and expect it to churn.
- `.gitignore` is the union of a hand-written list and GitHub's Godot template. `export_credentials.cfg` is ignored deliberately: it holds export signing keys and store passwords. Do not un-ignore it.
- `.claude/settings.json` is checked in and shared (permissions only). `.claude/settings.local.json` is gitignored and holds this machine's tool paths. Never move a path from the second file into the first.
- Scene (`.tscn`) and resource (`.tres`) files are text and hand-editable, but Godot rewrites node ordering and UIDs on save — prefer editing them through the editor when the change is structural. Hand-written `.tscn` files must have `load_steps` equal to the number of `ext_resource` + `sub_resource` blocks plus one.
- `.gd.uid` files are generated alongside scripts and **are** committed; Godot uses them to keep references stable when files move.
