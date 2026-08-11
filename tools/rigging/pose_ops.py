"""The pose vocabulary shared by every character's clip spec. No Blender, no character.

`bl_author_anims.py` is the driver and owns everything that touches `bpy`; `clips_<name>.py`
is one character's constants. This module is the third piece: the handful of pure functions a
spec module needs *while it is being defined*, which therefore cannot live in the driver -
importing the driver would run Blender.

## Why poses are written as world axes

`bl_normalize_rig.py` guarantees one invariant: every bone's local Z faces the character's
front. Local Y runs along the bone, so local X - the flexion axis - falls out of the bone's
own direction and therefore points a *different world direction on every bone*: world -X on
the spine, +X on the legs, and roughly vertical on the arms. Writing poses as raw local
angles needs a fresh sign convention per bone and is how a day gets lost.

So a pose is a list of rotations about **world** axes, and `Pose.rotate` in the driver
converts each one into the bone's local frame. World axes have one meaning each, for every
bone:

    +X  sagittal    forward/back swing. Rotating a joint about +X moves everything
                    *below* it forward and everything *above* it backward - so a thigh
                    swings forward on +X, a spine leans forward on -X, a knee flexes on -X.
    +Y  frontal     raise/lower and side bend. +Y raises the left arm and lowers the right.
    +Z  transverse  twist - pelvis and shoulder counter-rotation, toe-in/toe-out.

Two extra axis names cover what world axes cannot say:

    twist   about the bone's own current direction - a wrist roll, an axial arm roll
    bend    about the bone's own current local X - the normalizer's flexion axis

and two more ops move a bone rather than turning it:

    loc     a world-space offset, written into the bone's local frame
    pivot   shift the bone so its rotation reads as happening about a given point

Ops apply in the order listed and compose. The rest pose is a **T-pose**, so every clip starts
from the spec's `STANCE` layer, which brings the arms down; clip poses are deltas layered on
top of it.

## Mirroring

Left/right pairs take the *same* sign about world X and *opposite* signs about Y and Z,
because the mirror plane is the character's own sagittal plane. `swap_sides()` applies that.

## Keyframe tuples and easing

A clip is a list of `(frame, delta)` or `(frame, delta, ease)`. **`ease` controls the interval
from that key to the *next* one**, not the arrival into it - that is Blender's own
`keyframe_point.interpolation` semantics, and matching it means what you read here is what the
graph editor shows.

Omit `ease` and Blender's default applies: BEZIER with auto-clamped handles, i.e. an ease-out
*and* an ease-in on every pose. That default is why the knight's first swing was floaty - the
exporter force-samples at 30 fps and bakes the easing into the file, so the blade decelerated
into the pose where it was supposed to connect. `idle`, `run`, `roll` and `jump` still use it
and should: they have no single moment that has to be the fastest.

The vocabulary a swing needs:

    "CONSTANT"              a true hold - the pose does not move until the next key
    "LINEAR"                constant speed, for carrying a blade through an arc
    ("EXPO", "EASE_IN")     accelerate, slowly then hard - the strike into contact
    ("EXPO", "EASE_OUT")    decelerate hard then slowly - settling into a coil
    ("BACK", "EASE_OUT")    overshoot and come back - the follow-through past centre
    ("SINE", "EASE_OUT")    a gentle settle - recovering into a guard
"""

# Blender's F-Curve interpolation modes and easing directions. Restated rather than read off
# `bpy` so a spec module stays importable without Blender - `bl_author_anims.py` is the only
# thing here that needs it running.
INTERPOLATIONS = frozenset({
    "CONSTANT", "LINEAR", "BEZIER",
    "SINE", "QUAD", "CUBIC", "QUART", "QUINT", "EXPO", "CIRC",
    "BACK", "BOUNCE", "ELASTIC",
})
EASINGS = frozenset({"AUTO", "EASE_IN", "EASE_OUT", "EASE_IN_OUT"})


def layered(*layers):
    """Stack pose layers: a bone's ops from each layer run in the order the layers are given."""
    out = {}
    for layer in layers:
        for bone, ops in layer.items():
            out.setdefault(bone, []).extend(ops)
    return out


def swap_sides(delta):
    """Exchange the character's left and right - a run's second half is its first.

    Reflecting through the sagittal plane leaves a sagittal (world X) rotation alone and
    reverses everything else, along with any sideways offset. Only cyclic locomotion should
    use this; a stance holding a weapon in one hand is asymmetric on purpose.
    """
    out = {}
    for bone, ops in delta.items():
        name = bone.replace("Left", "\0").replace("Right", "Left").replace("\0", "Right")
        flipped = []
        for kind, value in ops:
            if kind in ("loc", "pivot"):
                flipped.append((kind, (-value[0], value[1], value[2])))
            elif kind == "X":
                flipped.append((kind, value))
            else:
                flipped.append((kind, -value))
        out[name] = flipped
    return out


def normalize_ease(ease):
    """`None`, `"LINEAR"` or `("EXPO", "EASE_IN")` -> `None` or `(interpolation, easing)`.

    Validated here rather than at keyframe-writing time: a typo'd mode is silently ignored by
    Blender's RNA assignment in some builds, and a swing that quietly kept its default Bezier
    easing is exactly the bug this whole mechanism exists to prevent.
    """
    if ease is None:
        return None
    interpolation, easing = (ease, "AUTO") if isinstance(ease, str) else ease
    if interpolation not in INTERPOLATIONS:
        raise ValueError(f"unknown interpolation {interpolation!r}; "
                         f"expected one of {sorted(INTERPOLATIONS)}")
    if easing not in EASINGS:
        raise ValueError(f"unknown easing {easing!r}; expected one of {sorted(EASINGS)}")
    return interpolation, easing


def unpack_key(key):
    """A clip entry as `(frame, delta, ease)`, accepting the two-item form."""
    if len(key) == 2:
        return key[0], key[1], None
    frame, delta, ease = key
    return frame, delta, normalize_ease(ease)
