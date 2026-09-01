#!/usr/bin/env python3
"""Join CarChassis geometry + CarPhysics grip via car-name anchors in CarDef."""
import struct, json, re
import numpy as np
from pathlib import Path
A9=Path(r"C:\Users\player\Desktop\A9 sifugc")
OUT=Path(r"C:\Users\player\Desktop\a9模型")
cardef=(A9/"project/scratch/reference/vehicle-gdb/CarDef.gdb").read_bytes()
ch=(A9/"project/scratch/reference/vehicle-gdb/CarChassis.gdb").read_bytes()
cp=(A9/"project/scratch/reference/vehicle-gdb/CarPhysics.gdb").read_bytes()
def table(d):
    for co in range(max(0,len(d)-32*2000), len(d)-3, 4):
        c=struct.unpack_from("<I",d,co)[0]
        if not 1<=c<=2000 or co+4+c*32!=len(d): continue
        t=co+4
        return [dict(zip(("i","key","off","size","tag"),(i,)+struct.unpack_from("<QQQQ",d,t+i*32))) for i in range(c)]
CH,CP=table(ch),table(cp)
def posmap(descs):
    m={}
    for d in descs:
        p=cardef.find(struct.pack("<Q", d["key"]))
        if p>=0: m[p]=d
    return m
chp,cpp=posmap(CH),posmap(CP)
chk,cpk=np.array(sorted(chp)),np.array(sorted(cpp))
# 以车名为锚：名字后面 0x600 内的第一个 CP key 和第一个 CH key
NAME=re.compile(rb"[A-Z][A-Za-z0-9 _\-'&\.]{3,45}")
rows=[]; seen=set()
for m in NAME.finditer(cardef):
    s=m.group()
    if b"/" in s or b"_NPC" in s: continue
    pos=m.start()
    jc=np.searchsorted(cpk,pos); jh=np.searchsorted(chk,pos)
    if jc>=len(cpk) or jh>=len(chk): continue
    kc,kh=int(cpk[jc]),int(chk[jh])
    if kc-pos>0x600 or kh-pos>0x600: continue
    d_cp,d_ch=cpp[kc],chp[kh]
    if d_cp["off"] in seen: continue
    n=d_ch["size"]//4
    if n<21: continue
    g=struct.unpack_from(f"<{n}f", ch, d_ch["off"])
    mass,trF,trR,wb,cg=g[0],g[4],g[5],g[6],g[14]
    if not (500<=mass<=6000 and 1.0<=trF<=2.5 and -0.5<cg<0): continue
    sh=2 if d_cp["size"]==436 else (12 if d_cp["size"]==476 else 0)
    grip=struct.unpack_from("<f", cp, d_cp["off"]+(79+sh)*4)[0]
    gs  =struct.unpack_from("<f", cp, d_cp["off"]+(23+sh)*4)[0]
    if not (0.2<grip<2.5): continue
    seen.add(d_cp["off"])
    rows.append(dict(name=s.decode("utf-8","replace").strip(), mass=mass, trackF=trF, trackR=trR,
                     wheelbase=wb, cg=cg, grip=grip, gs=gs, wheelie=grip*abs(cg)/trF))
json.dump(rows, open(OUT/"03-车辆档案"/"chassis-geometry.json","w",encoding="utf-8"), indent=1, ensure_ascii=False)
w=np.array([r["wheelie"] for r in rows])
print(f"关联成功 {len(rows)} 台")
print(f"载荷转移指数: min={w.min():.4f} 中位={np.median(w):.4f} max={w.max():.4f}\n")
o=np.argsort(-w)
print(f"{'车名':<32}{'质量':>7}{'轮距':>7}{'重心':>8}{'抓地':>7}{'极速':>6}{'指数':>8}")
print("=== 最易抬轮 TOP12 ===")
for k in o[:12]:
    r=rows[k]; print(f"{r['name'][:30]:<32}{r['mass']:7.0f}{r['trackF']:7.3f}{r['cg']:8.3f}{r['grip']:7.3f}{r['gs']:6.0f}{r['wheelie']:8.4f}")
print("=== 最贴地 BOTTOM10 ===")
for k in o[-10:]:
    r=rows[k]; print(f"{r['name'][:30]:<32}{r['mass']:7.0f}{r['trackF']:7.3f}{r['cg']:8.3f}{r['grip']:7.3f}{r['gs']:6.0f}{r['wheelie']:8.4f}")
