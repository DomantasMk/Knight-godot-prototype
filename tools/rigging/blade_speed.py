"""Forward-kinematic the sword tip through a clip, and assert the swing's shape.

    python tools/rigging/blade_speed.py <file.glb> [--clip attack] [--impact 7] [--gates]

`glb_inspect.py` answers "did the file survive the last step". This answers the question that
actually decides whether a swing reads: **where in the clip is the blade fastest, and is that
where the game says it connects?**

The eye reads contact where motion is fastest. The knight's original swing failed that: the
tip peaked at 37.2 m/s entering frame 6 and the Call Method track fired at frame 8, by which
point it was down to 15.5 m/s - 42 % of peak. Nothing in the pipeline could have caught it,
because `bl_author_anims.py` reports *poses* and the fault is in the *spacing between* them.
Blender's exporter force-samples at 30 fps with LINEAR glTF samplers, which bakes the default
auto-Bezier easing into the file: the blade eases into the pose where it hits something. A
pose report cannot see that. This runs FK over the sampled frames the file actually contains,
so it sees exactly what Godot will play.

That makes "impact must be on the speed peak" an assertion instead of a judgement call, which
is the same trade this project already made for foot height and blade direction. Run it on any
re-authored `attack` before Stage 5, and again on the shipped GLB afterwards.

## What it measures

The `WeaponSocket` node's world transform every sampled frame, composed down the glTF node
chain from the scene root - so it includes every animated bone between the hips and the hand.
The blade runs along the socket's local +Y for `--length` metres (1.0, `sword_lowpoly.glb`
pommel butt to tip), giving a tip position per frame; speed is the difference between
consecutive frames over the frame interval.

Everything is in the **file's own scene space**, which for this project is also the player's
local space: `player.tscn` puts `Model` under `Visuals` under `Player` with no transform on
either, so a tip position here is directly comparable to the Hitbox sphere's centre.

## The phases, derived not assumed

Frame numbers are not hardcoded, so a re-timed clip does not need this script edited:

    peak    the fastest frame in the clip
    apex    the slowest frame between the start and the peak - the coil/strike boundary,
            which is where a swing naturally has its velocity minimum, and where the target
            shape puts a deliberate CONSTANT hold
    coil    frames 1..apex
    strike  frames apex+1..impact
    follow  frames impact+1..impact+--follow-frames, the window the stall gate watches

The tail after that is deliberately excluded: a clip is *supposed* to slow down as it settles
into its end pose, and the state machine crossfades out over it anyway.
"""
import argparse
import bisect
import json
import math
import struct
import sys

MAGIC = 0x46546C67          # "glTF"
JSON_CHUNK = 0x4E4F534A     # "JSON"
BIN_CHUNK = 0x004E4942      # "BIN\0"

# Blade axis and length: sword_lowpoly.glb is 1.0 m pommel butt to tip, along the socket's
# local +Y. Restated from bl_author_anims.py's SWORD_LENGTH; --length overrides it.
BLADE_AXIS = (0.0, 1.0, 0.0)

# The player's Hitbox sphere, read off entities/player/player.tscn: a SphereShape3D of radius
# 1.1 on a CollisionShape3D at (0, 1, -1). Player forward is -Z, so that is one metre ahead
# and one metre up. Model space is player space here - see the module docstring.
HITBOX_CENTRE = (0.0, 1.0, -1.0)
HITBOX_RADIUS = 1.1

COMPONENT = {
    5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2),
    5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4),
}
TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


# ------------------------------------------------------------------------ container access
def read_glb(path):
    """Return (gltf dict, binary buffer). GLB keeps buffer 0 in the BIN chunk, with no uri."""
    with open(path, "rb") as f:
        data = f.read()
    magic, _version, _length = struct.unpack("<III", data[:12])
    if magic != MAGIC:
        raise SystemExit(f"[blade] {path} is not a binary glTF file")
    gltf, binary, offset = None, b"", 12
    while offset < len(data):
        size, kind = struct.unpack("<II", data[offset:offset + 8])
        payload = data[offset + 8:offset + 8 + size]
        if kind == JSON_CHUNK and gltf is None:
            gltf = json.loads(payload)
        elif kind == BIN_CHUNK and not binary:
            binary = payload
        offset += 8 + size
    if gltf is None:
        raise SystemExit(f"[blade] {path} has no JSON chunk")
    return gltf, binary


def read_accessor(gltf, binary, index):
    """One accessor as a list of tuples (or floats for SCALAR).

    Handles the interleaved case via the bufferView's byteStride, which animation data never
    uses in practice but vertex data does - cheaper to support than to detect and reject.
    """
    accessor = gltf["accessors"][index]
    fmt, size = COMPONENT[accessor["componentType"]]
    count = TYPE_COUNT[accessor["type"]]
    element = size * count

    view = gltf["bufferViews"][accessor.get("bufferView", 0)]
    if view.get("buffer", 0) != 0:
        raise SystemExit("[blade] only GLB-embedded buffer 0 is supported")
    stride = view.get("byteStride") or element
    base = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)

    out = []
    for i in range(accessor["count"]):
        start = base + i * stride
        values = struct.unpack_from("<" + fmt * count, binary, start)
        out.append(values[0] if count == 1 else values)
    return out


# ------------------------------------------------------------------------------ 4x4 maths
IDENTITY4 = ((1.0, 0.0, 0.0, 0.0),
             (0.0, 1.0, 0.0, 0.0),
             (0.0, 0.0, 1.0, 0.0),
             (0.0, 0.0, 0.0, 1.0))


def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4))
                 for i in range(4))


def transform_point(m, p):
    """Affine only - these matrices never carry a projection row."""
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3))


def trs_matrix(t, q, s):
    x, y, z, w = q
    r = (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )
    return tuple(tuple(r[i][j] * s[j] for j in range(3)) + (t[i],) for i in range(3)) + \
        ((0.0, 0.0, 0.0, 1.0),)


def normalize4(q):
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return tuple(c / n for c in q)


def slerp(a, b, u):
    dot = sum(p * q for p, q in zip(a, b))
    if dot < 0.0:                       # take the short way round
        b, dot = tuple(-c for c in b), -dot
    if dot > 0.9995:                    # nearly parallel: lerp, or sin(theta0) goes to zero
        return normalize4(tuple(p + (q - p) * u for p, q in zip(a, b)))
    theta0 = math.acos(max(-1.0, min(1.0, dot)))
    theta = theta0 * u
    s0 = math.sin(theta0 - theta) / math.sin(theta0)
    s1 = math.sin(theta) / math.sin(theta0)
    return tuple(p * s0 + q * s1 for p, q in zip(a, b))


# ------------------------------------------------------------------------- node + sampling
def parents_of(gltf):
    parent = {}
    for index, node in enumerate(gltf.get("nodes", [])):
        for child in node.get("children", []):
            parent[child] = index
    return parent


def find_node(gltf, name):
    for index, node in enumerate(gltf.get("nodes", [])):
        if node.get("name") == name:
            return index
    raise SystemExit(f"[blade] no node named {name!r} in the file")


def rest_trs(node):
    """A node's own transform. `matrix` is column-major in glTF; TRS is the common case."""
    if "matrix" in node:
        m = node["matrix"]
        return tuple(tuple(m[j * 4 + i] for j in range(4)) for i in range(4))
    return trs_matrix(node.get("translation", [0.0, 0.0, 0.0]),
                      node.get("rotation", [0.0, 0.0, 0.0, 1.0]),
                      node.get("scale", [1.0, 1.0, 1.0]))


def channels_for(gltf, binary, animation):
    """{node index: {path: (times, values, interpolation)}} for one animation."""
    out = {}
    for channel in animation.get("channels", []):
        target = channel["target"]
        if "node" not in target:
            continue
        sampler = animation["samplers"][channel["sampler"]]
        interpolation = sampler.get("interpolation", "LINEAR")
        if interpolation == "CUBICSPLINE":
            raise SystemExit("[blade] CUBICSPLINE samplers are not supported - re-export "
                             "with export_optimize_animation_size=False")
        times = read_accessor(gltf, binary, sampler["input"])
        values = read_accessor(gltf, binary, sampler["output"])
        out.setdefault(target["node"], {})[target["path"]] = (times, values, interpolation)
    return out


def sample(track, t):
    times, values, interpolation = track
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    i = max(0, bisect.bisect_right(times, t) - 1)
    if interpolation == "STEP":
        return values[i]
    span = times[i + 1] - times[i]
    u = (t - times[i]) / span if span > 0.0 else 0.0
    if len(values[i]) == 4:             # rotation, the only VEC4 track glTF animates
        return slerp(values[i], values[i + 1], u)
    return tuple(a + (b - a) * u for a, b in zip(values[i], values[i + 1]))


def node_matrix(gltf, tracks, index, t):
    node = gltf["nodes"][index]
    animated = tracks.get(index)
    if not animated:
        return rest_trs(node)
    return trs_matrix(
        sample(animated["translation"], t) if "translation" in animated
        else node.get("translation", [0.0, 0.0, 0.0]),
        sample(animated["rotation"], t) if "rotation" in animated
        else node.get("rotation", [0.0, 0.0, 0.0, 1.0]),
        sample(animated["scale"], t) if "scale" in animated
        else node.get("scale", [1.0, 1.0, 1.0]),
    )


def frame_times(animation, gltf, binary):
    """The frames the file actually contains, not a guessed fps.

    Blender exports these force-sampled, so the union of every sampler's input times is the
    authored frame grid - reading it back beats assuming 30 and being wrong on a re-timed clip.
    """
    times = set()
    for sampler in animation.get("samplers", []):
        times.update(read_accessor(gltf, binary, sampler["input"]))
    return sorted(times)


# ---------------------------------------------------------------------------------- the run
def tip_track(path, clip, socket_name, length):
    """Per-frame (time, socket origin, blade tip) for one clip."""
    gltf, binary = read_glb(path)
    animations = {a.get("name", f"<{i}>"): a for i, a in enumerate(gltf.get("animations", []))}
    if clip not in animations:
        raise SystemExit(f"[blade] no clip {clip!r} - have {', '.join(animations) or 'none'}")
    animation = animations[clip]

    parent = parents_of(gltf)
    chain = [find_node(gltf, socket_name)]
    while chain[-1] in parent:
        chain.append(parent[chain[-1]])
    chain.reverse()                     # root first, socket last

    tracks = channels_for(gltf, binary, animation)
    blade = tuple(c * length for c in BLADE_AXIS)

    frames = []
    for t in frame_times(animation, gltf, binary):
        world = IDENTITY4
        for index in chain:
            world = mat_mul(world, node_matrix(gltf, tracks, index, t))
        frames.append((t, transform_point(world, (0.0, 0.0, 0.0)),
                       transform_point(world, blade)))
    return frames, chain, gltf


def distance(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def phases(speeds, impact, follow_frames, last):
    """peak, apex, and the follow-through window - all derived, none hardcoded.

    The apex is *not* simply the slowest frame before the peak: every clip starts from rest,
    so that would always pick frame 1 and report a one-frame coil. The coil has its own
    velocity crest partway through - the arm is travelling to get into the wind-up pose - and
    the boundary is the trough after it. So: find where the initial rise first stops rising,
    then take the minimum between there and the peak.
    """
    peak = max(range(len(speeds)), key=lambda i: speeds[i])
    crest = next((i for i in range(1, peak) if speeds[i] >= speeds[i + 1]), None)
    apex = min(range(crest, peak + 1), key=lambda i: speeds[i]) if crest else 1
    return peak, apex, crest, min(last, impact + follow_frames)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("glb")
    parser.add_argument("--clip", default="attack", help="clip to measure")
    parser.add_argument("--socket", default="WeaponSocket", help="node the blade hangs off")
    parser.add_argument("--length", type=float, default=1.0, help="blade length in metres")
    parser.add_argument("--impact", type=int, default=None,
                        help="frame the Call Method track fires on; required by --gates")
    parser.add_argument("--follow-frames", type=int, default=5,
                        help="frames after impact the stall gate watches (default 5)")
    parser.add_argument("--gates", action="store_true",
                        help="assert the swing's shape and exit non-zero on failure")
    parser.add_argument("--quiet", action="store_true", help="gate verdicts only, no table")
    args = parser.parse_args()

    frames, chain, gltf = tip_track(args.glb, args.clip, args.socket, args.length)
    if len(frames) < 3:
        raise SystemExit(f"[blade] clip {args.clip!r} has {len(frames)} frames - nothing to say")

    times = [f[0] for f in frames]
    tips = [f[2] for f in frames]
    travel = [0.0] + [distance(tips[i - 1], tips[i]) for i in range(1, len(tips))]
    speeds = [0.0] + [travel[i] / (times[i] - times[i - 1]) if times[i] > times[i - 1] else 0.0
                      for i in range(1, len(times))]

    last = len(frames) - 1
    fps = last / times[-1] if times[-1] > 0 else 0.0
    impact = args.impact if args.impact is not None else None
    peak, apex, crest, follow_end = phases(speeds, impact if impact is not None else last,
                                           args.follow_frames, last)

    names = [gltf["nodes"][i].get("name", f"<{i}>") for i in chain]
    print(f"{args.glb}  clip {args.clip!r}  {times[-1]:.3f} s  "
          f"{len(frames)} frames (~{fps:.0f} fps)")
    print(f"[blade] chain {' > '.join(names)}")
    print(f"[blade] blade +Y x {args.length:.2f} m, hitbox sphere at "
          f"{HITBOX_CENTRE} r {HITBOX_RADIUS}")

    if not args.quiet:
        print(f"\n  {'f':>3} {'time':>6} {'speed':>7} {'travel':>7}  "
              f"{'tip x':>6} {'tip y':>6} {'tip z':>6}  {'hitbox':>7}  phase")
        for i, (t, _origin, tip) in enumerate(frames):
            if impact is None:
                tag = ""
            elif i == impact:
                tag = "IMPACT"
            elif i <= apex:
                tag = "coil"
            elif i <= impact:
                tag = "strike"
            elif i <= follow_end:
                tag = "follow"
            else:
                tag = "tail"
            mark = "*" if i == peak else " "
            print(f"  {i:>3} {t:>6.3f} {speeds[i]:>7.2f}{mark}{travel[i]:>7.3f}  "
                  f"{tip[0]:>6.2f} {tip[1]:>6.2f} {tip[2]:>6.2f}  "
                  f"{distance(tip, HITBOX_CENTRE):>7.2f}  {tag}")
        print(f"\n[blade] peak {speeds[peak]:.1f} m/s entering frame {peak}; "
              f"total tip path {sum(travel):.2f} m")
        if crest is None:
            print("[blade] no velocity crest before the peak - this clip has no distinct "
                  "coil, so the coil/strike split below is meaningless")
        else:
            print(f"[blade] coil crests at f{crest}, apex (coil/strike boundary) at f{apex}")

    if not args.gates:
        return 0
    if impact is None:
        parser.error("--gates needs --impact")

    coil = sum(travel[1:apex + 1])
    strike = sum(travel[apex + 1:impact + 1])
    impact_ratio = speeds[impact] / speeds[peak] if speeds[peak] > 0 else 0.0
    reach = distance(tips[impact], HITBOX_CENTRE)

    # Three consecutive frames the blade barely moves is the "arm rotates, sword parks" fault:
    # the joint rotations cancel at the tip and the swing's most important moment goes still.
    #
    # Tested on the three frames *combined* rather than each one separately. The knight's
    # original stall ran 0.136 / 0.050 / 0.017 m, and a per-frame threshold of 0.10 m lets the
    # first of those through and so misses the very fault this gate was written for. A tenth
    # of a metre per frame averaged over the window is the same intent without the loophole.
    STALL_WINDOW = 3
    STALL_METRES = 0.10 * STALL_WINDOW
    stall = None
    for i in range(apex, follow_end - STALL_WINDOW + 2):
        if sum(travel[i:i + STALL_WINDOW]) < STALL_METRES:
            stall = i
            break

    checks = [
        ("impact on the speed peak",
         f"{speeds[impact]:.1f} m/s at f{impact} = {impact_ratio:.0%} of peak "
         f"{speeds[peak]:.1f} at f{peak}",
         impact_ratio >= 0.85, "want >= 85%"),
        ("no stall f%d-f%d" % (apex, follow_end),
         "clear" if stall is None else
         f"f{stall}-f{stall + STALL_WINDOW - 1} move "
         f"{sum(travel[stall:stall + STALL_WINDOW]):.2f} m combined",
         stall is None, f"want no {STALL_WINDOW} consecutive frames under "
                        f"{STALL_METRES:.2f} m combined"),
        ("coil smaller than strike",
         f"coil f1-f{apex} {coil:.2f} m vs strike f{apex + 1}-f{impact} {strike:.2f} m "
         f"= {coil / strike:.0%}" if strike > 0 else "strike covers no distance",
         strike > 0 and coil <= 0.60 * strike, "want <= 60%"),
        ("tip inside the hitbox at impact",
         f"{reach:.2f} m from centre",
         reach <= HITBOX_RADIUS, f"want <= {HITBOX_RADIUS}"),
    ]

    print()
    failed = 0
    for label, measured, ok, want in checks:
        if not ok:
            failed += 1
        print(f"[blade] {'PASS' if ok else 'FAIL'}  {label:<26} {measured}"
              f"{'' if ok else '   (' + want + ')'}")
    if failed:
        print(f"\n[blade] {failed} of {len(checks)} gates failed", file=sys.stderr)
    else:
        print(f"\n[blade] all {len(checks)} gates pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
