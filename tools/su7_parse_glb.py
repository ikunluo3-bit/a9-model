#!/usr/bin/env python3
"""SU7 glb → 世界空间点云（M3 第一步）。

解析 glTF 2.0（JSON+BIN），遍历节点树组合 4×4 变换，
输出每个 mesh-primitive 的世界空间顶点/UV/材质名 + 全局统计。
供投影器把 AMG 顶点贴到 SU7 表面。
"""
from __future__ import annotations
import struct, json, sys, io
from pathlib import Path
import numpy as np

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GLB = Path(r"C:\Users\player\Downloads\2025_xiaomi_su7_ultra.glb")
OUT = Path(r"build\jmox_work\su7_cloud.npz")

COMP = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(p: Path):
    d = p.read_bytes()
    jlen = struct.unpack_from("<I", d, 12)[0]
    g = json.loads(d[20:20 + jlen])
    bofs = 20 + jlen
    blen, btype = struct.unpack_from("<II", d, bofs)
    assert btype == 0x004E4942
    return g, d[bofs + 8:bofs + 8 + blen]


def accessor(g, bin_chunk, idx):
    a = g["accessors"][idx]
    v = g["bufferViews"][a["bufferView"]]
    ncomp = NCOMP[a["type"]]
    fmt = COMP[a["componentType"]]
    item = np.dtype("<" + fmt).itemsize
    stride = max(v.get("byteStride") or ncomp * item, ncomp * item)
    off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    cnt = a["count"]
    dt = np.dtype({"names": [f"c{i}" for i in range(ncomp)],
                   "formats": ["<" + fmt] * ncomp,
                   "offsets": [i * item for i in range(ncomp)],
                   "itemsize": stride})
    arr = np.frombuffer(bin_chunk, dtype=dt, count=cnt, offset=off)
    return np.stack([arr[f"c{i}"] for i in range(ncomp)], axis=1).astype(np.float64)


def node_matrix(n):
    if "matrix" in n:
        m = np.array(n["matrix"], dtype=np.float64).reshape(4, 4)
        return m.T          # glTF 列主序
    m = np.eye(4)
    if "scale" in n:
        m[:3, :3] = np.diag(n["scale"])
    if "rotation" in n:
        x, y, z, w = n["rotation"]
        R = np.array([
            [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        m[:3, :3] = R @ m[:3, :3]
    if "translation" in n:
        m[:3, 3] = n["translation"]
    return m


def main() -> int:
    g, bin_chunk = read_glb(GLB)
    nodes = g["nodes"]
    world = {}

    def walk(ni, parent_m):
        n = nodes[ni]
        m = parent_m @ node_matrix(n)
        if "mesh" in n:
            for pi, prim in enumerate(g["meshes"][n["mesh"]]["primitives"]):
                pos = accessor(g, bin_chunk, prim["attributes"]["POSITION"])
                uv = (accessor(g, bin_chunk, prim["attributes"]["TEXCOORD_0"])
                      if "TEXCOORD_0" in prim["attributes"] else np.zeros((len(pos), 2)))
                w = np.ones(len(pos))
                pos_w = (m @ np.hstack([pos, np.ones((len(pos), 1))]).T).T[:, :3]
                mat = prim.get("material")
                mname = g["materials"][mat].get("name", f"mat{mat}") if mat is not None else "none"
                key = mname
                if key in world:
                    world[key] = (np.vstack([world[key][0], pos_w]),
                                  np.vstack([world[key][1], uv]))
                else:
                    world[key] = (pos_w, uv)
        for c in n.get("children", []):
            walk(c, m)

    for root in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(root, np.eye(4))

    print(f"{'材质':<22}{'顶点':>9}  bbox 尺寸 (X/Y/Z)")
    total = 0
    for k, (v, uv) in sorted(world.items(), key=lambda x: -len(x[1][0])):
        total += len(v)
        dims = v.max(axis=0) - v.min(axis=0)
        print(f"{k:<22}{len(v):>9,}  {dims.round(2)}")
    print(f"合计 {total:,} 顶点，{len(world)} 材质")

    allv = np.vstack([v for v, _ in world.values()])
    print("全局 bbox min:", allv.min(axis=0).round(3), " max:", allv.max(axis=0).round(3))

    arrays = {}
    for i, (k, (v, uv)) in enumerate(world.items()):
        arrays[f"v{i}"] = v.astype(np.float32)
        arrays[f"uv{i}"] = uv.astype(np.float32)
    arrays["names"] = np.array(list(world.keys()))
    OUT.parent.mkdir(exist_ok=True)
    np.savez_compressed(OUT, **arrays)
    print("已存", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
