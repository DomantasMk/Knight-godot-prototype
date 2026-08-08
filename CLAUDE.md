# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An empty Godot 4.7 project (`KnightPrototype`) — the scaffolding exists but no scenes, scripts, or main scene have been created yet. There is no README, no test suite, and no build tooling beyond Godot itself.

## Project configuration (`project.godot`)

These settings are already chosen and shape how new code should be written:

- **Renderer**: Forward+, with the Direct3D 12 rendering driver on Windows (`rendering_device/driver.windows="d3d12"`).
- **3D physics**: Jolt Physics (not the legacy Godot Physics). Behavior of joints, damping, and layer masks differs from the default engine — check Jolt-specific docs when tuning.
- **Stretch**: `canvas_items` mode with `expand` aspect, i.e. resolution-independent 2D/UI that gains screen area rather than letterboxing on wider displays.

There is no `run/main_scene` set yet; the first scene added should register one here.

## Commands

Godot is not on `PATH` in this environment, so invoke the editor binary by full path (adjust for the installed version):

```powershell
# Open the project in the editor
& "C:\path\to\Godot_v4.7-stable_win64.exe" --path .

# Run the project headless-ish from the CLI (once a main scene exists)
& "C:\path\to\Godot_v4.7-stable_win64.exe" --path . 

# Run a specific scene
& "C:\path\to\Godot_v4.7-stable_win64.exe" --path . res://path/to/scene.tscn

# Reimport assets / regenerate .godot without opening the UI
& "C:\path\to\Godot_v4.7-stable_win64.exe" --path . --headless --import
```

## Notes

- `.godot/` is generated (imports, shader cache, UID cache) and gitignored — never edit it, and expect it to churn.
- `install.cmd` at the repo root is the Claude Code Windows installer script, unrelated to the game. Leave it alone or delete it; do not treat it as project tooling.
- Scene (`.tscn`) and resource (`.tres`) files are text and hand-editable, but Godot rewrites node ordering and UIDs on save — prefer editing them through the editor when the change is structural.
