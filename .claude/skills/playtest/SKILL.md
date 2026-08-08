---
name: playtest
description: Run KnightPrototype in a real window, drive it with scripted input, assert on game state, and capture screenshots. ONLY invoke when the user explicitly asks to playtest, run, or see the game — never on your own initiative to check work, and never as part of a larger task unless the user asked for it in that task.
---

# Playtest harness

Boots a scene, replays Input Map actions on a timeline, asserts on live game state, and
writes screenshots to `local/playtest/`. This is how a change gets verified *in the running
game* rather than by reading code.

## When this may run

**Only when the user asks for it.** Explicit requests look like: "playtest that", "run the
game", "does it actually work", "show me", "screenshot it", "/playtest".

**Do not run it** to satisfy your own uncertainty about a change, as a victory-lap check
after implementing something, or because a task felt visual. Finish the code, say what you
did *not* verify at runtime, and offer to playtest. The user decides.

Why the restriction: every run opens a real window on the user's desktop for several
seconds, stealing focus, and every screenshot read costs ~250 tokens that then ride along
in context for the rest of the session. Neither cost is the user's choice if you invoke
this unasked.

## Running it

```powershell
& $env:GODOT_BIN_CONSOLE --path . res://tools/playtest/playtest.tscn -- `
    "--scene=res://levels/level_01/level_01.tscn" `
    '--steps=wait 0.5; hold move_forward 1.2; expect get_node(''%Player'').is_on_floor(); tap attack; wait 0.12; shot swing'
```

Defaults: `--scene` is `level_01`, `--out` is `res://local/playtest`, `--scale` is `0.5`.
Requires `GODOT_BIN_CONSOLE`, so the session must have started at the repo root.

Steps, semicolon-separated:

| Step | |
|---|---|
| `wait <s>` | let the game run |
| `tap <action>` | press and release over one frame |
| `hold <action> <s>` | press, wait, release |
| `press` / `release <action>` | leave an action held / let it go |
| `expect <expression>` | assert true, else fail the run (exit 1) |
| `show <expression>` | print a value, no pass/fail |
| `shot <name>` | capture `<out>/<NN>_<name>.png` |

`expect` / `show` evaluate against the booted scene's **root**, so unique names resolve:
`get_node('%Trees').get_child_count() == 26`. **Single quotes only** — PowerShell mangles
nested double quotes and you get `Unterminated String`.

## Assert first; screenshot only for appearance

`expect` is the default tool. It costs ~20 tokens, fails the run instead of waiting to be
noticed, and does not accumulate in context. Counts, health, on-floor, the chop counter —
assertions.

Screenshots are the *correct* tool when the question is genuinely about appearance: does
the swing arc read as a swing, is the camera framed sensibly, did a material or shadow
break, does the scene look like anything. There is no property to assert on there — do not
contort those into assertions, and do not skip the image to save tokens.

Most runs want both: assertions for mechanics, one shot for the look.

## Screenshot budget

- Leave `--scale` at 0.5 (576×324, ~250 tokens). The HUD counter and body positions stay
  legible. Raise to `--scale=1` only for fine detail, and say why.
- Capture the one frame that decides the question, not a strip.
- The PNGs persist in `local/playtest/` (gitignored). Context does not need to hold them —
  in a long session `/compact` drops accumulated images, and any shot still worth seeing
  can be re-read from disk. Never re-run the harness to recover a screenshot you have.

## Notes

- Runs in a **real window** by necessity: `--headless` uses the dummy renderer and every
  capture comes back blank.
- Exits non-zero if any `expect` failed, so it doubles as a smoke test.
- The harness lives at `tools/playtest/`; the full step reference is its docstring.
