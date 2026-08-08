# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`KnightPrototype` — an early-stage **3D** Godot 4.7 game prototype. The scaffolding, autoloads, Input Map, and a greybox test level exist; no gameplay does yet. There is no test suite and no build tooling beyond Godot itself.

Remote: https://github.com/DomantasMk/Knight-godot-prototype (branch `main`).

## Directory layout

Co-located feature folders — a feature's scene, script, and helpers live together, so a feature can be moved or deleted as one directory. `assets/` is the exception and stays sorted by type.

```
assets/{audio/{music,sfx},fonts,models,textures}/   raw art and audio
autoloads/                                          singletons (see below)
entities/{player,enemy}/                            <name>.tscn + <name>.gd together
levels/{level_01,main_menu}/                        one folder per level
systems/                                            cross-cutting logic with no scene of its own
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
- **Main scene**: `res://levels/level_01/level_01.tscn` — a greybox (40×40 floor, directional light, procedural sky, camera, `PlayerSpawn` marker). It exists so F5 always does something; replace it freely.

## Commands

Godot is not on `PATH`. The installed binary is:

```powershell
$godot = "C:\Users\doman\Downloads\Godot_v4.7.1-stable_win64.exe\Godot_v4.7.1-stable_win64.exe"

& $godot --path .                                  # open in the editor
& $godot --path . res://path/to/scene.tscn         # run one scene
& $godot --path . --headless --import              # reimport / regenerate .godot
& $godot --path . --headless --quit-after 60       # smoke-test: run 60 frames, print errors
```

Use the sibling `..._console.exe` instead when you need stdout/stderr captured on the command line — the plain `.exe` detaches from the console on Windows. The last two commands are the cheapest way to verify a change did not break scene loading or parsing.

## Notes

- `.godot/` is generated (imports, shader cache, UID cache) and gitignored — never edit it, and expect it to churn.
- `.gitignore` is the union of a hand-written list and GitHub's Godot template. `export_credentials.cfg` is ignored deliberately: it holds export signing keys and store passwords. Do not un-ignore it.
- `install.cmd` at the repo root is the Claude Code Windows installer script, unrelated to the game. Leave it alone or delete it; do not treat it as project tooling.
- Scene (`.tscn`) and resource (`.tres`) files are text and hand-editable, but Godot rewrites node ordering and UIDs on save — prefer editing them through the editor when the change is structural. Hand-written `.tscn` files must have `load_steps` equal to the number of `ext_resource` + `sub_resource` blocks plus one.
- `.gd.uid` files are generated alongside scripts and **are** committed; Godot uses them to keep references stable when files move.
