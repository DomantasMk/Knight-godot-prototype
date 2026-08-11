"""Repair the rotation of a bone-parented node in a GLB, which Blender exports wrong.

    python tools/rigging/glb_fix_socket.py <file.glb> [--node WeaponSocket] [--check]

Blender's glTF exporter converts an object's *translation* from Z-up to Y-up but writes its
*rotation* verbatim in Blender's frame, for an object whose `parent_type` is `BONE`. The
`WeaponSocket` empty therefore arrives in Godot rotated 90 degrees about X: the blade axis
that pointed up in Blender points along +Z, i.e. straight out of the knight's back, and the
0.18 m grip inset that should drop the sword into the fist drops it below and behind the
hand instead. That is the whole of "the sword is backwards and not in the hand".

**The bug is symmetric, and that is why it survived review.** Blender's *importer* makes the
same omission in reverse, so a Blender -> glTF -> Blender round trip is stable and every
number `bl_author_anims.py` prints - blade within 8 degrees of vertical through `idle` - is
correct about what Blender holds and silently wrong about what the file says. Only a
consumer that reads the glTF literally, which is to say Godot, ever sees it.

So the fix cannot live in Blender, and it cannot live at the end of Stage 3 either: the
normalized GLB is read straight back into Blender by Stage 4, whose importer would apply the
same wrong conversion to a corrected file and hand the animation author a socket pointing
forward and about 30 cm out of the fist - the rotation is applied before the offset from the
bone, so getting it wrong moves the node too. It has to be the last thing that happens to the
file, after every Blender step. Re-exporting from that mis-read scene still produces a
correct file, because the two mistakes cancel; only what Blender shows and prints is wrong,
which is why `bl_author_anims.py` restates the socket's rest matrix instead of reading it.

What "correct" means: the node's rotation is rewritten so that its **global** rotation in
the file's own rest pose is `--target`, default identity - blade up, flat of the blade to
the character's side, which is the neutral carry `bl_normalize_rig.py` places it in.
Translation and scale are left alone; the exporter already gets those right.
"""
import argparse
import json
import math
import struct
import sys

MAGIC = 0x46546C67          # "glTF"
JSON_CHUNK = 0x4E4F534A     # "JSON"

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


# ------------------------------------------------------------------------ container access
def read_glb(path):
    """Return (gltf dict, [(chunk_type, payload), ...]) with the JSON chunk left in place."""
    with open(path, "rb") as f:
        data = f.read()
    magic, version, _length = struct.unpack("<III", data[:12])
    if magic != MAGIC:
        raise ValueError(f"{path} is not a binary glTF file")
    chunks = []
    offset = 12
    while offset < len(data):
        size, kind = struct.unpack("<II", data[offset:offset + 8])
        chunks.append((kind, data[offset + 8:offset + 8 + size]))
        offset += 8 + size
    if not chunks or chunks[0][0] != JSON_CHUNK:
        raise ValueError(f"{path} does not start with a JSON chunk")
    return json.loads(chunks[0][1]), chunks, version


def write_glb(path, gltf, chunks, version):
    """Rewrite the container with a new JSON chunk, every other chunk carried over as-is."""
    body = b""
    for index, (kind, payload) in enumerate(chunks):
        if index == 0:
            payload = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
            payload += b" " * (-len(payload) % 4)
        else:
            payload += b"\x00" * (-len(payload) % 4)
        body += struct.pack("<II", len(payload), kind) + payload
    with open(path, "wb") as f:
        f.write(struct.pack("<III", MAGIC, version, 12 + len(body)) + body)


# ------------------------------------------------------------------------------- 3x3 maths
def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def transpose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def orthonormalize(m):
    """Gram-Schmidt on the columns. Exported bases carry ~1e-6 of scale noise."""
    cols = [[m[0][j], m[1][j], m[2][j]] for j in range(3)]
    out = []
    for col in cols:
        for done in out:
            dot = sum(c * d for c, d in zip(col, done))
            col = [c - dot * d for c, d in zip(col, done)]
        norm = math.sqrt(sum(c * c for c in col)) or 1.0
        out.append([c / norm for c in col])
    return tuple(tuple(out[j][i] for j in range(3)) for i in range(3))


def quat_to_mat(q):
    x, y, z, w = q
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )


def mat_to_quat(m):
    """Shepperd's method: pick the largest diagonal term so the divisor never vanishes."""
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2][1] - m[1][2]) / s
        y = (m[0][2] - m[2][0]) / s
        z = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        w = (m[2][1] - m[1][2]) / s
        x = 0.25 * s
        y = (m[0][1] + m[1][0]) / s
        z = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        w = (m[0][2] - m[2][0]) / s
        x = (m[0][1] + m[1][0]) / s
        y = 0.25 * s
        z = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        w = (m[1][0] - m[0][1]) / s
        x = (m[0][2] + m[2][0]) / s
        y = (m[1][2] + m[2][1]) / s
        z = 0.25 * s
    return (x, y, z, w)


# ---------------------------------------------------------------------------- node walking
def parents_of(gltf):
    parent = {}
    for index, node in enumerate(gltf.get("nodes", [])):
        for child in node.get("children", []):
            parent[child] = index
    return parent


def node_rotation(node):
    return orthonormalize(quat_to_mat(node.get("rotation", [0.0, 0.0, 0.0, 1.0])))


def global_rotation(gltf, parent, index):
    """Rest-pose rotation of a node in scene space, parents composed outward."""
    m = node_rotation(gltf["nodes"][index])
    while index in parent:
        index = parent[index]
        m = mat_mul(node_rotation(gltf["nodes"][index]), m)
    return orthonormalize(m)


def find_node(gltf, name):
    for index, node in enumerate(gltf.get("nodes", [])):
        if node.get("name") == name:
            return index
    raise SystemExit(f"[socket] no node named {name!r} in the file")


def describe(m):
    axes = ("+X", "+Y", "+Z")
    return "  ".join(f"{axes[j]}->({m[0][j]:+.3f},{m[1][j]:+.3f},{m[2][j]:+.3f})"
                     for j in range(3))


def max_error(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(3) for j in range(3))


# ----------------------------------------------------------------------------------- entry
def fix_socket(path, name="WeaponSocket", target=IDENTITY, check_only=False):
    """Rewrite `name`'s local rotation so its global rest rotation is `target`.

    Returns the error that was present before the fix, so a caller can tell a real repair
    from a no-op on an already-correct file.
    """
    gltf, chunks, version = read_glb(path)
    parent = parents_of(gltf)
    index = find_node(gltf, name)
    if index not in parent:
        raise SystemExit(f"[socket] {name!r} has no parent - it is not bone-parented")

    before = global_rotation(gltf, parent, index)
    error = max_error(before, target)
    print(f"[socket] {name} under {gltf['nodes'][parent[index]].get('name')!r}")
    print(f"[socket]   is:     {describe(before)}")
    print(f"[socket]   wanted: {describe(target)}")
    if error < 1e-4:
        print(f"[socket] already correct (max error {error:.2e}), nothing written")
        return error
    if check_only:
        print(f"[socket] FAIL: off by {error:.4f} - rerun without --check to repair")
        return error

    # local = inverse(parent global) * target. The parent chain is rigid, so the inverse of
    # its rotation is its transpose.
    bone = global_rotation(gltf, parent, parent[index])
    gltf["nodes"][index]["rotation"] = [round(v, 9) for v in
                                        mat_to_quat(mat_mul(transpose(bone), target))]
    write_glb(path, gltf, chunks, version)

    gltf, chunks, version = read_glb(path)
    after = global_rotation(gltf, parents_of(gltf), index)
    residual = max_error(after, target)
    if residual > 1e-5:
        raise SystemExit(f"[socket] rewrite did not take: still off by {residual:.6f}")
    print(f"[socket]   now:    {describe(after)}")
    print(f"[socket] fixed {path} (was off by {error:.4f}, now {residual:.2e})")
    return error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb")
    parser.add_argument("--node", default="WeaponSocket", help="node to repair")
    parser.add_argument("--target", default="",
                        help="wanted global basis as 9 comma-separated row-major numbers; "
                             "default is identity")
    parser.add_argument("--check", action="store_true",
                        help="report and exit non-zero instead of writing")
    args = parser.parse_args()

    target = IDENTITY
    if args.target:
        values = [float(v) for v in args.target.split(",")]
        if len(values) != 9:
            parser.error("--target needs exactly 9 numbers")
        target = orthonormalize(tuple(tuple(values[i * 3:i * 3 + 3]) for i in range(3)))

    error = fix_socket(args.glb, args.node, target, check_only=args.check)
    return 1 if args.check and error >= 1e-4 else 0


if __name__ == "__main__":
    sys.exit(main())
