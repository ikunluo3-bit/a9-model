#!/usr/bin/env python3
"""外观移植：把 A 车的模型/贴图/碰撞/动画/音效整套接到 B 车的资源路径上。

**原理**
    Pegasus manifest 每行:
        path_hash : project_hash : 逻辑路径 : (C:大小|NC:-) : (X:密钥|NX:-) : asset_id
    引擎按**逻辑路径**查表拿到 `asset_id`，再去读 `assets/main/<asset_id>`。
    把受体那几行的 `asset_id` 换成供体的 —— 逻辑路径、哈希全不动，
    引擎照旧问"科迈罗的模型"，**拿到的是女武神的字节**。

`asset_id` 固定 16 位十六进制，**替换前后行长一字节不差**，
所以 manifest 重新加密后大小不变，回封时不必动其他任何东西。

用法:
  python visualswap.py --plan                       # 只看映射
  python visualswap.py --out manifest-swapped.txt   # 写出改好的 manifest 明文
"""
from __future__ import annotations
import argparse, json, re, sys, io
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

G = Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k")
LINE = re.compile(r"^(\d+):(\d+):(.*?):(NC:-|C:\d+):(NX:-|X:\d+):([0-9A-F]{16})$")

# 车辆资源特征表。A9 的资源命名极不统一（同一台车四种拼法、变体与本体混用），
# 所以每台车要写明: pat=包含, excl=排除, prefer=同一角色有多个候选时优先谁
CARS = {
    "camaro-lt": dict(name="Chevrolet Camaro LT",
                      pat=re.compile(r"(?i)camaro_?LT|Camaro_LT_2")),
    "valkyrie":  dict(name="Aston Martin Valkyrie",
                      pat=re.compile(r"(?i)Aston_Martin_Valkyrie|AM_Valkyrie"),
                      excl=re.compile(r"(?i)lego|custom_shockwave|nitro_exhaust|battle_tapes")),
    "fordzilla-p1": dict(name="Ford Team Fordzilla P1",
                         pat=re.compile(r"(?i)fordzilla"),
                         excl=re.compile(r"(?i)custom_shockwave|livery|tire_")),
    "jesko-ab":  dict(name="Koenigsegg Jesko Absolut (杰AB)",
                      pat=re.compile(r"(?i)koenigsegg_jesko|Koegnisegg_Jesko"),
                      excl=re.compile(r"(?i)lego|custom_shockwave|nitro_exhaust|livery|tire_"),
                      # Absolut 与普通版共用一套命名，优先挑 Absolut/Absolute 的
                      prefer=re.compile(r"(?i)absolut")),
}


def role(path: str) -> str | None:
    """把逻辑路径归到一个与车名无关的角色上，供两车对齐。"""
    if "/collisions/" in path: return "collision"
    if "/gfx3D/cars/animations/" in path:
        return "anim_brake" if "brake" in path else "anim"
    if "/gfx3D/cars/models/" in path:
        if "_fx_overclocked_dyn" in path: return "fx_overclocked"
        if "_fx_respawn_dyn" in path:     return "fx_respawn"
        if "_car.json" in path:           return "model"
        return None
    if "/gfx3D/fx/models/fx_shockwave_lines" in path: return "shockwave"
    m = re.search(r"/gfx3D/cars/textures/car_.*?_((?:carpaint|details|emissive_mesh|glass|LOD)"
                  r"(?:_[A-Za-z0-9]+)*)\.tga", path)
    if m: return "tex:" + m.group(1)
    if "/sounds/" in path:
        return "sound_npc" if path.endswith("_NPC") else "sound"
    return None


def load():
    out = []
    for ln in (G / "manifest.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.fullmatch(ln)
        if m:
            out.append(dict(raw=ln, path=m.group(3), c=m.group(4), x=m.group(5), asset=m.group(6)))
    return out


def collect(ent, spec):
    """按角色收集；同角色多个候选时 prefer 命中的优先。"""
    got = {}
    for e in ent:
        if not spec["pat"].search(e["path"]): continue
        if spec.get("excl") and spec["excl"].search(e["path"]): continue
        r = role(e["path"])
        if not r: continue
        pref = bool(spec.get("prefer") and spec["prefer"].search(e["path"]))
        if r not in got or (pref and not got[r][1]):
            got[r] = (e, pref)
    return {r: v[0] for r, v in got.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--donor", default="valkyrie", choices=sorted(CARS))
    ap.add_argument("--recipient", default="camaro-lt", choices=sorted(CARS))
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--assets", help="写出 {受体asset_id: 供体asset_id} —— 用于直接换内容，"
                                     "而不是改 manifest 指向")
    ap.add_argument("--skip", nargs="*", default=[], help="不换的角色，如 sound sound_npc")
    a = ap.parse_args()

    ent = load()
    RECIPIENT, DONOR = CARS[a.recipient], CARS[a.donor]
    rec = collect(ent, RECIPIENT)
    don = collect(ent, DONOR)

    print(f"受体 {RECIPIENT['name']}: {len(rec)} 个角色")
    print(f"供体 {DONOR['name']}: {len(don)} 个角色\n")
    print(f"{'角色':<24}{'受体 asset':>18}{'供体 asset':>20}   状态")
    swap, miss = {}, []
    for r in sorted(rec):
        if r in a.skip:
            print(f"{r:<24}{rec[r]['asset']:>18}{'—':>20}   跳过"); continue
        if r not in don:
            miss.append(r); print(f"{r:<24}{rec[r]['asset']:>18}{'—':>20}   **供体缺**"); continue
        if rec[r]["c"] != don[r]["c"] or rec[r]["x"] != don[r]["x"]:
            print(f"{r:<24}   压缩/加密标志不一致，跳过"); continue
        swap[rec[r]["asset"]] = don[r]["asset"]
        print(f"{r:<24}{rec[r]['asset']:>18}{don[r]['asset']:>20}   换")
    only = sorted(set(don) - set(rec))
    if only: print(f"\n供体独有（受体没有对应路径，无需处理）: {only}")
    if miss: print(f"供体缺失: {miss}")
    print(f"\n合计替换 {len(swap)} 个 asset_id")

    if a.out:
        src = (G / "manifest.txt").read_text(encoding="utf-8", errors="replace")
        lines = src.splitlines(keepends=True)
        n = 0
        for i, ln in enumerate(lines):
            m = LINE.fullmatch(ln.rstrip("\r\n"))
            if not m: continue
            if not RECIPIENT["pat"].search(m.group(3)): continue
            old = m.group(6)
            if old in swap:
                lines[i] = ln.replace(old, swap[old]); n += 1
        new = "".join(lines)
        assert len(new) == len(src), f"长度变了 {len(src)} -> {len(new)}"
        Path(a.out).write_text(new, encoding="utf-8", newline="")
        print(f"\n改写 {n} 行，长度不变（{len(new):,} 字符）-> {a.out}")
        Path(a.out + ".map.json").write_text(json.dumps(swap, indent=1), encoding="utf-8")


    if a.assets:
        Path(a.assets).write_text(json.dumps(swap, indent=1), encoding="utf-8")
        print(f"资源映射 -> {a.assets}")


if __name__ == "__main__":
    main()
