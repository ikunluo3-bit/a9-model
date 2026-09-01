#!/usr/bin/env python3
"""扫全部车模的节点/材质名，找出与受体兼容的供体。

假设：供体模型若含有受体车辆配置里没有的部件/材质，引擎按名查参数会拿到空 optional。
所以「供体节点集 ⊆ 受体节点集」的车才是安全供体。
"""
import zipfile, re, sys, io, json, collections
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

APK = r"C:\Users\player\Desktop\A9 sifugc\output\A9-600300-6.0.0k-base.apk"
MAN = Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k\manifest.txt")
LINE = re.compile(r"^(\d+):(\d+):(.*?):(NC:-|C:\d+):(NX:-|X:\d+):([0-9A-F]{16})$")
KEEP = re.compile(r"^(bone_|detach_|glass_|lights_|emissive|engine_|nitro_|chassis|trail_|wheel|carpaint|exhaust|<root>)", re.I)

z = zipfile.ZipFile(APK)
models = {}
for ln in MAN.read_text(encoding="utf-8", errors="replace").splitlines():
    m = LINE.fullmatch(ln)
    if not m: continue
    p = m.group(3)
    if "/gfx3D/cars/models/" not in p or "_car.json" not in p: continue
    if "custom_shockwave" in p: continue
    models[p.split("/|/")[-1].replace("_car.json.jmodel", "")] = m.group(6)

print(f"车模 {len(models)} 个，开始读…")
nodes = {}
for i, (nm, aid) in enumerate(models.items()):
    d = bytes(c ^ 0xAB for c in z.read("assets/main/" + aid))
    nodes[nm] = {x.group().decode() for x in re.finditer(rb"[A-Za-z_<][A-Za-z0-9_\.>]{3,50}", d)
                 if KEEP.match(x.group().decode())}
    if (i + 1) % 80 == 0: print(f"  {i+1}/{len(models)}")

CAM = next(k for k in nodes if "Camaro_LT" in k)
base = nodes[CAM]
print(f"\n受体 {CAM}: {len(base)} 个节点\n")
rows = [(len(v - base), len(base - v), k) for k, v in nodes.items() if k != CAM]
rows.sort()
print(f"{'多出的节点数':>10}{'缺少的':>8}  车模")
for extra, missing, k in rows[:25]:
    print(f"{extra:>10}{missing:>8}  {k[:60]}")
subsets = [k for e, m, k in rows if e == 0]
print(f"\n**节点集完全是科迈罗子集的车模: {len(subsets)} 个**")
for k in subsets[:20]: print("   ", k)
Path(r"C:\Users\player\Desktop\a9模型\03-车辆档案\model-nodes.json").write_text(
    json.dumps({k: sorted(v) for k, v in nodes.items()}, ensure_ascii=False, indent=0), encoding="utf-8")
