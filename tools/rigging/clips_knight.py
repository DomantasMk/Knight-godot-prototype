"""The knight's clip spec — every number that is about *this character* and no other.

Consumed by `bl_author_anims.py`, which owns the Blender machinery and the report:

    blender -b -P tools/rigging/bl_author_anims.py -- <src.glb> <dst.glb> knight

Split out of the driver because Stage 4 is a tune-run-read loop, and the loop was editing a
several-hundred-line script to change one number - every read and every diff of which rode
along in the agent's context for the rest of its window. Copy this file to `clips_<name>.py`
for a new character; the driver, `pose_ops.py` and the report are generic and stay put.

The pose vocabulary — world axes, `twist`/`bend`, `loc`/`pivot`, layering, mirroring, and the
easing modes — is documented in `pose_ops.py`. Read that first; nothing here will parse
without it.

Five clips, one Blender Action each:

    idle    2.0s  loop    breathing, weight shift, the sword arm drifting
    run     0.6s  loop    contact / down / airborne, twice, sides exchanged
    attack  0.6s  once    coil, hold, strike, follow-through past centre, open guard
    roll    0.7s  once    tuck, a full forward revolution, recover
    jump    0.6s  once    push-off, extension, knees up at apex, reach down, land absorbed

**All clips are in-place.** Translation stays driven by the velocity code in `player.gd`; the
only translation authored here is the vertical bob of the Hips, which is animation, not travel.

Clip names and lengths are load-bearing outside this file: they become the AnimationTree's
state names in `entities/player/player.tscn`, the `LOOP_MODES` keys in
`tools/import/knight_rigged_import.gd`, and the constant lists in both `verify_*.gd`. Renaming
one here without the other four is a silent failure.
"""
from pose_ops import layered, swap_sides

# sword_lowpoly.glb is 1.0 m from pommel butt to tip, blade along the socket's local +Y.
SWORD_LENGTH = 1.0

# The rest pose is a T-pose. STANCE is the character standing: arms brought down out of the
# T, the sword arm folded up into a guard with the blade vertical. Every clip layers on it.
#
# The right arm is the fiddly one. The socket's blade axis is perpendicular to the forearm
# (that is how a fist holds a grip), so a blade cannot point up while the arm hangs - it
# needs the elbow folded until the forearm is roughly horizontal, and then a wrist roll to
# bring the blade off horizontal and up. -90 is that roll; the residual tilt is about 1 deg.
STANCE = {
    "Spine":         [("X", -2)],
    "Chest":         [("X", -2)],
    "Neck":          [("X", 3)],

    "LeftUpperArm":  [("Y", -66), ("X", 6)],
    "LeftLowerArm":  [("X", 28)],
    "LeftHand":      [("twist", 15)],

    "RightUpperArm": [("Y", 62), ("X", 8)],
    "RightLowerArm": [("X", 80)],
    "RightHand":     [("twist", -90)],

    "LeftUpperLeg":  [("X", 2)],
    "LeftLowerLeg":  [("X", -6)],
    "LeftFoot":      [("X", 4)],
    "RightUpperLeg": [("X", 2)],
    "RightLowerLeg": [("X", -6)],
    "RightFoot":     [("X", 4)],
}

# --- idle: a 2 s breath. Small, but not so small it reads as a frozen mesh under a
# camera that never moves. The sword arm drifts on its own cycle so the two never line up.
IDLE = [
    (0, {}),
    (15, {
        "Spine":         [("X", 3)],
        "Chest":         [("X", 3)],
        "Neck":          [("X", -2)],
        "LeftUpperArm":  [("Y", -4)],
        "RightUpperArm": [("Y", 3), ("X", -4)],
        "Hips":          [("loc", (0.0, 0.0, 0.014))],
    }),
    (30, {
        "Spine":         [("X", -2)],
        "Chest":         [("X", -1)],
        "Hips":          [("Z", -3), ("loc", (0.008, 0.0, -0.006))],
        "LeftUpperArm":  [("X", 4)],
        "RightUpperArm": [("X", -6)],
        "RightLowerArm": [("X", 5)],
    }),
    (45, {
        "Spine":         [("X", 2)],
        "Chest":         [("X", 2)],
        "Neck":          [("X", -1)],
        "Hips":          [("Z", 2), ("loc", (-0.004, 0.0, 0.008))],
        "LeftUpperArm":  [("Y", -2)],
        "RightUpperArm": [("Y", 2), ("X", -2)],
    }),
    (60, {}),
]

# --- run: contact / down / airborne, then the same three with the sides exchanged.
# The sword arm swings less than the free arm - it is carrying a metre of steel.
#
# Swinging a straight leg forward lifts the foot faster than intuition suggests - the hip
# is only 0.88 m up and the leg is 0.74 m, so 34 degrees of thigh puts the foot 13 cm off
# the ground. With no root motion and no foot IK the planted foot slides anyway, so the
# bar here is simply that it must not visibly float: the report keeps the planted toe
# within a few centimetres of its rest height, and the amplitudes below are what that costs.
RUN_CONTACT = {
    "Hips":          [("Z", -7), ("loc", (0.0, 0.0, -0.008))],
    "Spine":         [("X", -9)],
    "Chest":         [("X", -3), ("Z", 14)],
    "LeftUpperLeg":  [("X", 22)],
    "LeftLowerLeg":  [("X", -10)],
    "LeftFoot":      [("X", 2)],
    "RightUpperLeg": [("X", -26)],
    "RightLowerLeg": [("X", -40)],
    "RightFoot":     [("X", 22)],
    "LeftUpperArm":  [("X", -34)],
    "LeftLowerArm":  [("X", 22)],
    "RightUpperArm": [("X", 20)],
    "RightLowerArm": [("X", -14)],
}
RUN_DOWN = {
    "Hips":          [("Z", -3), ("loc", (0.0, 0.0, -0.035))],
    "Spine":         [("X", -11)],
    "Chest":         [("X", -3), ("Z", 7)],
    "LeftUpperLeg":  [("X", 6)],
    "LeftLowerLeg":  [("X", -22)],
    "LeftFoot":      [("X", 14)],
    "RightUpperLeg": [("X", -32)],
    "RightLowerLeg": [("X", -58)],
    "RightFoot":     [("X", 28)],
    "LeftUpperArm":  [("X", -18)],
    "LeftLowerArm":  [("X", 30)],
    "RightUpperArm": [("X", 10)],
    "RightLowerArm": [("X", -6)],
}
RUN_AIR = {
    "Hips":          [("Z", -5), ("loc", (0.0, 0.0, 0.045))],
    "Spine":         [("X", -10)],
    "Chest":         [("X", -3), ("Z", 11)],
    "LeftUpperLeg":  [("X", -28)],
    "LeftLowerLeg":  [("X", -46)],
    "LeftFoot":      [("X", 26)],
    "RightUpperLeg": [("X", 16)],
    "RightLowerLeg": [("X", -66)],
    "RightFoot":     [("X", 30)],
    "LeftUpperArm":  [("X", -12)],
    "LeftLowerArm":  [("X", 34)],
    "RightUpperArm": [("X", 6)],
    "RightLowerArm": [("X", -4)],
}
RUN = [
    (0, RUN_CONTACT),
    (3, RUN_DOWN),
    (6, RUN_AIR),
    (9, swap_sides(RUN_CONTACT)),
    (12, swap_sides(RUN_DOWN)),
    (15, swap_sides(RUN_AIR)),
    (18, RUN_CONTACT),
]

# --- attack: a diagonal slash from over the right shoulder down across to the left.
# 18 frames, 0.60 s. Contact is posed AND wired at frame 8 = 0.267 s: the per-key easing
# below puts the tip's speed peak on that frame instead of a frame and a half before it,
# which is what the old 15-frame version needed the Call Method track pulled back for.
#
# The shape, and why each easing is what it is:
#     f0  EXPO/OUT   snap into the coil, then settle - a wind-up should not drift
#     f3  CONSTANT   a true hold: the beat that lets the eye read the wind-up
#     f5  SINE/IN    accelerate all the way into contact and never let up. NOT EXPO/IN,
#                    which is what the shape was drafted with: over a 3-frame strike EXPO
#                    puts 84% of the tip's travel in the last frame alone (measured: 2.13 m
#                    of 2.53 m), which leaves f6 with 0.037 m and trips blade_speed.py's
#                    stall gate at f4-f6 - the CONSTANT hold either side of it is 0.00 m by
#                    construction, so the first strike frame has to carry the whole window.
#                    SINE/IN is the gentlest EASE_IN available and still peaks on contact.
#     f8  LINEAR     carry the blade through the follow-through at speed
#    f10  BACK/OUT   overshoot past centre
#    f13  SINE/OUT   settle into an open guard, deliberately NOT back to stance:
#                    the state machine crossfades attack -> idle/run over 0.15 s, and
#                    animating all the way home animates the recovery twice.
#
# Gate the exported GLB, not this file - a pose report cannot see spacing:
#     python tools/rigging/blade_speed.py <animated.glb> --clip attack --impact 8 --gates
ATTACK = [
    (0, {}, ("EXPO", "EASE_OUT")),
    (3, {                                   # coil: tight, blade high on the knight's right
        # The torso counter-twist is what decides whether the blade is visible: it rotates the
        # whole arm about the spine, and the tip sits ~1.2 m out, so every degree of it is
        # ~2 cm of tip. The old clip wound -42 deg of Hips+Spine+Chest and put the tip 1.17 m
        # behind the knight, where a 56 deg overhead camera only sees his own back. -21 deg
        # keeps the coil on his right. Same reason X is -8 and not +14: with the arm already
        # above the shoulder, +X is what tips it over behind the head.
        "Hips":          [("Z", -6)],
        "Spine":         [("X", 2), ("Z", -5)],
        "Chest":         [("Z", -10)],
        "RightUpperArm": [("Y", -104), ("X", -8)],
        "RightLowerArm": [("X", -24)],
        "RightHand":     [("twist", 34)],
        "LeftUpperArm":  [("X", 26)],
        "LeftLowerArm":  [("X", 12)],
        "LeftUpperLeg":  [("X", -5)],
        "RightUpperLeg": [("X", 5)],
    }, "CONSTANT"),
    (5, {                                   # the same pose again: the hold reads as a beat
        "Hips":          [("Z", -6)],
        "Spine":         [("X", 2), ("Z", -5)],
        "Chest":         [("Z", -10)],
        "RightUpperArm": [("Y", -104), ("X", -8)],
        "RightLowerArm": [("X", -24)],
        "RightHand":     [("twist", 34)],
        "LeftUpperArm":  [("X", 26)],
        "LeftLowerArm":  [("X", 12)],
        "LeftUpperLeg":  [("X", -5)],
        "RightUpperLeg": [("X", 5)],
    }, ("SINE", "EASE_IN")),
    (8, {                                   # contact: blade out front, still accelerating
        "Hips":          [("Z", 14)],
        "Spine":         [("X", -16), ("Z", 12)],
        "Chest":         [("Z", 26)],
        # Y +4, not the +26 that reads right on paper. Past centre the tip hangs off the far
        # side of the shoulder, so world +Y - the axis that lowers the right *arm* - lifts the
        # *tip*. Every degree of it fought the wrist and the swing went still. -Y carries the
        # tip down and across, which is the direction a chop is actually going.
        "RightUpperArm": [("Y", 4), ("X", 42)],
        "RightLowerArm": [("X", -58)],
        "RightHand":     [("twist", -72)],
        "LeftUpperArm":  [("X", -28)],
        "LeftLowerArm":  [("X", 10)],
        "LeftUpperLeg":  [("X", 10)],
        "RightUpperLeg": [("X", -8)],
    }, "LINEAR"),
    (10, {                                  # past centre: carried well left and lower
        "Hips":          [("Z", 25)],
        "Spine":         [("X", -22), ("Z", 23)],
        "Chest":         [("Z", 42)],
        "RightUpperArm": [("Y", -6), ("X", 12)],
        "RightLowerArm": [("X", -50)],
        "RightHand":     [("twist", -88)],
        "LeftUpperArm":  [("X", -36)],
        "LeftUpperLeg":  [("X", 13)],
        "RightUpperLeg": [("X", -11)],
    }, ("BACK", "EASE_OUT")),
    (11, {                                  # overshoot: a few degrees past f10
        "Hips":          [("Z", 28)],
        "Spine":         [("X", -25), ("Z", 26)],
        "Chest":         [("Z", 47)],
        "RightUpperArm": [("Y", -12), ("X", 4)],
        "RightLowerArm": [("X", -46)],
        "RightHand":     [("twist", -96)],
        "LeftUpperArm":  [("X", -40)],
        "LeftUpperLeg":  [("X", 14)],
        "RightUpperLeg": [("X", -12)],
    }),
    (13, {                                  # recoil: settle back toward f10
        "Hips":          [("Z", 22)],
        "Spine":         [("X", -20), ("Z", 20)],
        "Chest":         [("Z", 38)],
        "RightUpperArm": [("Y", -2), ("X", 16)],
        "RightLowerArm": [("X", -52)],
        "RightHand":     [("twist", -84)],
        "LeftUpperArm":  [("X", -32)],
        "LeftUpperLeg":  [("X", 11)],
        "RightUpperLeg": [("X", -9)],
    }, ("SINE", "EASE_OUT")),
    (18, {                                  # open guard: a third of the way home, blade left
        "Hips":          [("Z", 7)],
        "Spine":         [("X", -7), ("Z", 6)],
        "Chest":         [("Z", 12)],
        "RightUpperArm": [("Y", 24), ("X", 8)],
        "RightLowerArm": [("X", -16)],
        "RightHand":     [("twist", -36)],
        "LeftUpperArm":  [("X", -12)],
        "LeftUpperLeg":  [("X", 4)],
        "RightUpperLeg": [("X", -3)],
    }),
]

# --- roll: tuck into a ball and turn one full revolution forward.
# A forward roll takes the head down and forward, and world +X moves what is *above* a
# joint backward, so the revolution is about world -X. The clip is in-place, so the whole
# turn comes from the Hips - pivoted so the body tumbles around ROLL_PIVOT, roughly the
# centre of the tucked ball, instead of around the pelvis joint.
ROLL_PIVOT = (0.0, 0.15, 0.90)
TUCK = {
    "Spine":         [("X", -28)],
    "Chest":         [("X", -26)],
    "UpperChest":    [("X", -18)],
    "Neck":          [("X", -22)],
    "Head":          [("X", -14)],
    "LeftUpperLeg":  [("X", 112)],
    "LeftLowerLeg":  [("X", -132)],
    "LeftFoot":      [("X", 20)],
    "RightUpperLeg": [("X", 112)],
    "RightLowerLeg": [("X", -132)],
    "RightFoot":     [("X", 20)],
    "LeftUpperArm":  [("Y", -14), ("X", 46)],
    "LeftLowerArm":  [("X", 60)],
    "RightUpperArm": [("X", 40)],
    "RightLowerArm": [("X", 20)],
}


def tumble(degrees, drop, tuck=1.0):
    """The tucked body at `degrees` through the revolution, `drop` metres lower."""
    scaled = {bone: [(kind, value * tuck) for kind, value in ops] for bone, ops in TUCK.items()}
    return layered(scaled, {"Hips": [("X", degrees), ("pivot", ROLL_PIVOT),
                                     ("loc", (0.0, 0.0, drop))]})


# The last keyframe holds -360 rather than snapping back to 0: a key at 0 would make the
# f-curve unwind the whole revolution backwards over the final frames. -360 and 0 are the
# same orientation, and Godot's slerp handles the quaternion sign when blending out.
ROLL = [
    (0, {}),
    (3, tumble(-30, -0.30, tuck=0.85)),
    (7, tumble(-120, -0.42)),
    (11, tumble(-210, -0.42)),
    (15, tumble(-300, -0.38)),
    (18, tumble(-345, -0.18, tuck=0.55)),
    (21, {"Hips": [("X", -360)]}),
]

# --- jump: a short hop straight up. In place like everything else - the 0.8 m of travel is
# player.gd's velocity, and the only translation here is the push-off and landing squash.
#
# 18 frames is 0.60 s, which is deliberately the airtime player.gd produces (0.8 m under
# 1.8x gravity is 0.602 s), so the landing pose arrives on the frame the feet do. Retiming
# one without the other lands the knight in a mid-air pose or holds the squash in the air.
#
# There is no crouch anticipation, on purpose: the impulse is applied on the frame Space
# goes down, so a wind-up would show the knight sinking while he is already rising. Frame 0
# is the tail of a push-off instead - the ankles and knees still extending - and the 0.06 s
# crossfade in from idle/run covers it.
JUMP = [
    (0, {                                       # push-off: still folded, already extending
        "Hips":          [("loc", (0.0, 0.0, -0.065))],
        "Spine":         [("X", -7)],
        "Chest":         [("X", -4)],
        "LeftUpperLeg":  [("X", 12)],
        "LeftLowerLeg":  [("X", -32)],
        "LeftFoot":      [("X", 20)],
        "RightUpperLeg": [("X", 12)],
        "RightLowerLeg": [("X", -32)],
        "RightFoot":     [("X", 20)],
        "LeftUpperArm":  [("X", -24)],          # free arm back, about to throw upward
        "LeftLowerArm":  [("X", -10)],
        "RightUpperArm": [("X", -10)],
    }),
    (3, {                                       # extension: legs straight, toes pointed
        "Hips":          [("loc", (0.0, 0.0, 0.02))],
        "Spine":         [("X", 4)],
        "Chest":         [("X", 3)],
        "Neck":          [("X", -3)],
        "LeftUpperLeg":  [("X", -10)],
        "LeftLowerLeg":  [("X", -4)],
        "LeftFoot":      [("X", -28)],
        "RightUpperLeg": [("X", -10)],
        "RightLowerLeg": [("X", -4)],
        "RightFoot":     [("X", -28)],
        "LeftUpperArm":  [("Y", 20), ("X", 34)],   # thrown up and forward
        "LeftLowerArm":  [("X", 10)],
        "RightUpperArm": [("Y", -14), ("X", 12)],  # the sword arm lifts, but only a little
    }),
    (9, {                                       # apex: knees up, scissored so it is not a squat
        "Spine":         [("X", -6)],
        "Chest":         [("X", -4)],
        "Neck":          [("X", 4)],
        "LeftUpperLeg":  [("X", 46)],
        "LeftLowerLeg":  [("X", -84)],
        "LeftFoot":      [("X", -12)],
        "RightUpperLeg": [("X", 30)],
        "RightLowerLeg": [("X", -98)],
        "RightFoot":     [("X", -6)],
        "LeftUpperArm":  [("Y", 12), ("X", 14)],
        "LeftLowerArm":  [("X", 25)],
        "RightUpperArm": [("Y", -8)],
        "RightLowerArm": [("X", 6)],
    }),
    (13, {                                      # descent: still folded, starting to unfold
        "Hips":          [("loc", (0.0, 0.0, 0.01))],
        "Spine":         [("X", -3)],
        "LeftUpperLeg":  [("X", 28)],
        "LeftLowerLeg":  [("X", -52)],
        "RightUpperLeg": [("X", 18)],
        "RightLowerLeg": [("X", -60)],
        "RightFoot":     [("X", 4)],
        "LeftUpperArm":  [("Y", 6), ("X", -12)],
        "RightUpperArm": [("Y", -4)],
    }),
    (16, {                                      # reach: nearly straight, one frame off contact
        "LeftUpperLeg":  [("X", 6)],
        "LeftLowerLeg":  [("X", -12)],
        "LeftFoot":      [("X", 12)],
        "RightUpperLeg": [("X", 4)],
        "RightLowerLeg": [("X", -14)],
        "RightFoot":     [("X", 12)],
        "LeftUpperArm":  [("X", -20)],
        "RightUpperArm": [("X", -6)],
    }),
    (18, {                                      # absorb: knees take the landing, hips drop
        "Hips":          [("loc", (0.0, 0.0, -0.075))],
        "Spine":         [("X", -10)],
        "Chest":         [("X", -5)],
        "LeftUpperLeg":  [("X", 14)],
        "LeftLowerLeg":  [("X", -36)],
        "LeftFoot":      [("X", 22)],
        "RightUpperLeg": [("X", 14)],
        "RightLowerLeg": [("X", -36)],
        "RightFoot":     [("X", 22)],
        "LeftUpperArm":  [("Y", -6), ("X", -14)],
        "LeftLowerArm":  [("X", 14)],
        "RightUpperArm": [("X", -4)],
    }),
]

CLIPS = [
    ("idle", IDLE),
    ("run", RUN),
    ("attack", ATTACK),
    ("roll", ROLL),
    ("jump", JUMP),
]
