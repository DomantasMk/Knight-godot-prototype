# Knight-godot-prototype

An early-stage 3D game prototype in Godot 4.7 (Forward+, Jolt physics). One loop is
playable in greybox: a knight walks under a fixed Warcraft 3-style overhead camera and
swings at choppable trees. No art, no audio, no tests yet.

Open the project in Godot 4.7 and press F5 — `levels/level_01` is the main scene and
doubles as the demo harness. WASD moves, LMB swings.

`context/` holds short notes on why the project is shaped the way it is; `CLAUDE.md`
indexes them and covers the conventions.

The knight's mesh, rig and animation clips are produced by a separate repo,
[3d-asset-preparation-ai-pipeline](https://github.com/DomantasMk/3d-asset-preparation-ai-pipeline).
This one keeps the finished GLBs and the code that wires them into the game.
