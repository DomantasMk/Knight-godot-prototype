"""Report what is actually inside a GLB, and optionally fail if something is missing.

The rigging pipeline has three gates where the interesting question is "did the file
survive the last step with everything it needs" - after SkinTokens rigs a mesh, after
Blender writes the animation clips, and before the GLB is committed to assets/models/.
Reading the glTF JSON chunk answers all three in one pass and needs no Blender or Godot.

Colour is the one that bites: this project keeps albedo in COLOR_0 vertex colours with the
UVs deleted (see context/conventions.md), and several tools in the chain silently drop a
vertex colour attribute on re-export. A model missing COLOR_0 still imports and renders
pure white, so it has to be asserted rather than eyeballed.

    python tools/rigging/glb_inspect.py <file.glb> [--require skin,color,anim] [--tree]

Exits non-zero when a --require feature is absent, so it can gate a pipeline step.

`--tree` prints the joint hierarchy with each bone's rest position. A predicted skeleton
arrives with generic names (`bone_0` ... `bone_46`), so deciding whether it is usable, and
later mapping it onto humanoid names, can only be done from shape and position - the names
carry no information at all.
"""
import argparse
import json
import struct
import sys


def read_gltf_json(path):
    """Pull the JSON chunk out of a binary glTF container."""
    with open(path, "rb") as f:
        data = f.read()
    magic, _version, _length = struct.unpack("<III", data[:12])
    if magic != 0x46546C67:  # "glTF"
        raise ValueError(f"{path} is not a binary glTF file")
    chunk_len, chunk_type = struct.unpack("<II", data[12:20])
    if chunk_type != 0x4E4F534A:  # "JSON"
        raise ValueError(f"{path} does not start with a JSON chunk")
    return json.loads(data[20:20 + chunk_len]), len(data)


def triangle_count(gltf):
    """Sum triangles across every primitive, from index counts where present."""
    accessors = gltf.get("accessors", [])
    total = 0
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            if "indices" in prim:
                total += accessors[prim["indices"]]["count"] // 3
            elif "POSITION" in prim.get("attributes", {}):
                total += accessors[prim["attributes"]["POSITION"]]["count"] // 3
    return total


def animation_length(gltf, anim):
    """Duration is the largest keyframe time across the animation's input accessors."""
    accessors = gltf.get("accessors", [])
    longest = 0.0
    for sampler in anim.get("samplers", []):
        accessor = accessors[sampler["input"]]
        if accessor.get("max"):
            longest = max(longest, float(accessor["max"][0]))
    return longest


def print_joint_tree(gltf, skin):
    """Print the skin's joints as an indented tree with rest translations.

    glTF stores parenthood as each node's `children` list, so the parent map has to be
    inverted out of it. Translations are node-local, which is what matters here - a bone
    whose local offset is (0, 0.42, 0) off its parent is a spine segment no matter what it
    is called.
    """
    nodes = gltf.get("nodes", [])
    joints = skin.get("joints", [])
    joint_set = set(joints)

    parent = {}
    for index, node in enumerate(nodes):
        for child in node.get("children", []):
            parent[child] = index

    def walk(index, depth):
        node = nodes[index]
        name = node.get("name", f"<{index}>")
        t = node.get("translation", [0.0, 0.0, 0.0])
        print(f"    {'  ' * depth}{name}  ({t[0]:+.3f}, {t[1]:+.3f}, {t[2]:+.3f})")
        for child in node.get("children", []):
            if child in joint_set:
                walk(child, depth + 1)

    for index in joints:
        if parent.get(index) not in joint_set:
            walk(index, 0)


def describe(path, show_tree=False):
    gltf, byte_size = read_gltf_json(path)
    nodes = gltf.get("nodes", [])
    skins = gltf.get("skins", [])
    animations = gltf.get("animations", [])

    attributes = set()
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            attributes.update(prim.get("attributes", {}).keys())

    print(f"{path}  ({byte_size // 1024} KB)")
    print(f"  nodes      {len(nodes)}   meshes {len(gltf.get('meshes', []))}"
          f"   materials {len(gltf.get('materials', []))}")
    print(f"  triangles  {triangle_count(gltf)}")
    print(f"  attributes {sorted(attributes)}")

    if skins:
        for skin in skins:
            joints = skin.get("joints", [])
            names = [nodes[j].get("name", f"<{j}>") for j in joints]
            print(f"  skin       {len(joints)} joints")
            if show_tree:
                print_joint_tree(gltf, skin)
            else:
                print(f"    bones    {', '.join(names)}")
    else:
        print("  skin       none - mesh cannot deform")

    if animations:
        for anim in animations:
            name = anim.get("name", "<unnamed>")
            print(f"  animation  {name!r}  {animation_length(gltf, anim):.2f}s"
                  f"  {len(anim.get('channels', []))} channels")
    else:
        print("  animation  none")

    return {
        "skin": bool(skins),
        "color": "COLOR_0" in attributes,
        "anim": bool(animations),
        "joints": "JOINTS_0" in attributes and "WEIGHTS_0" in attributes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb")
    parser.add_argument(
        "--require",
        default="",
        help="comma-separated features to assert: skin, color, anim, joints",
    )
    parser.add_argument(
        "--tree",
        action="store_true",
        help="print the joint hierarchy with rest positions instead of a flat name list",
    )
    args = parser.parse_args()

    present = describe(args.glb, show_tree=args.tree)

    required = [r.strip() for r in args.require.split(",") if r.strip()]
    unknown = [r for r in required if r not in present]
    if unknown:
        parser.error(f"unknown --require value(s): {', '.join(unknown)}")

    missing = [r for r in required if not present[r]]
    if missing:
        print(f"\nFAIL: missing {', '.join(missing)}", file=sys.stderr)
        return 1
    if required:
        print(f"\nOK: {', '.join(required)} all present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
