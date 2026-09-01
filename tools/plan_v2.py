#!/usr/bin/env python3
"""四台车 v2：满改 + 顶层性能 + 操控拉到 90 档 + 每车风格差异化。"""
import argparse, hashlib, json, struct, sys, io
from pathlib import Path
if sys.platform=="win32": sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
GDB=Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k")
CH={"三菱":(1.43,-0.100),"Z4":(1.47,-0.160),"370Z":(1.785,-0.160),"拉法":(1.68,-0.150)}
# 车 -> (记录, 风格名, 覆盖项)
CARS={
 "三菱":("三菱 Lancer Evolution",0x1CE90,"轨道压路机 · 稳到底",
        dict(f76=0.55,f77=0.92, damp=0.60, steer=56500.0, gs=357.0, grip=1.153)),
 "Z4": ("宝马 Z4 LCI E89",      0x1933C,"翘头刀 · 又灵又爱抬",
        dict(f76=0.55,f77=0.95, damp=0.45, steer=56500.0, gs=357.0, grip=1.153)),
 "370Z":("日产 370Z",           0x19BB0,"轻量刀锋 · 全场最灵",
        dict(f76=0.60,f77=1.00, damp=0.50, steer=64000.0, gs=357.0, grip=1.153)),
 "拉法":("法拉利 LaFerrari",    0x1FBEC,"全能旗舰 · 均衡无短板",
        dict(f76=0.55,f77=0.93, damp=0.50, steer=56500.0, gs=357.0, grip=1.20)),
}
NITRO=[("单喷消耗",34,35,12.75,"d"),("单喷加成",36,37,4.229,"u"),("单喷维持",38,39,1850.0,"u"),
       ("橙喷消耗",42,43,25.5,"d"),("橙喷加成",44,45,12.69,"u"),("橙喷维持",46,47,1150.0,"u"),
       ("蓝喷消耗",50,51,32.62,"d"),("蓝喷加成",52,53,8.457,"u"),("蓝喷维持",54,55,7200.0,"u"),
       ("紫喷消耗",58,59,34.0,"d"),("紫喷加成",60,61,16.91,"u")]
def f32(v): return struct.unpack("<f",struct.pack("<f",v))[0]
def sha(b): return hashlib.sha256(b).hexdigest().upper()
raw=(GDB/"CarPhysics.gdb").read_bytes(); buf=bytearray(raw)
def rd(o,i): return struct.unpack_from("<f",raw,o+i*4)[0]
plan={}; touched=set()
for key,(full,off,style,ov) in CARS.items():
    rows=[]
    def put(nm,lo,hi,new):
        rows.append(dict(field=nm,lo=lo,hi=hi,b_lo=rd(off,lo),b_hi=rd(off,hi),after=f32(new)))
    put("极速",22,23,ov["gs"]); put("加速",72,73,2.6); put("抓地",78,79,ov["grip"])
    put("转向锐度",19,21,max(rd(off,21),ov["steer"]))
    put("操控76",76,76,ov["f76"]); put("操控77",77,77,ov["f77"])
    put("压缩阻尼",99,99,max(rd(off,99),ov["damp"])); put("回弹阻尼",100,100,max(rd(off,100),ov["damp"]))
    for nm,lo,hi,t,d in NITRO:
        cur=rd(off,hi); put(nm,lo,hi, max(cur,t) if d=="u" else min(cur,t))
    plan[key]=dict(full=full,off=off,style=style,rows=rows)
    for r in rows:
        for idx in {r["lo"],r["hi"]}:
            b=off+idx*4; struct.pack_into("<f",buf,b,r["after"]); touched|=set(range(b,b+4))
diff={i for i,(a,b) in enumerate(zip(raw,buf)) if a!=b}
stray=sorted(x for x in diff if x not in touched)
if stray: sys.exit(f"越界 {[hex(x) for x in stray[:6]]}")
ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true")
ap.add_argument("--out",default=r"C:\Users\player\Desktop\a9模型\tuned-v2")
a=ap.parse_args()
for k,p in plan.items():
    tr,cg=CH[k]
    g=[r for r in p["rows"] if r["field"]=="抓地"][0]
    h77=[r for r in p["rows"] if r["field"]=="操控77"][0]
    print(f"\n=== {p['full']} —— {p['style']} ===")
    for r in p["rows"]:
        if r["field"] in ("极速","加速","抓地","转向锐度","操控76","操控77","压缩阻尼","蓝喷加成"):
            k2=r["after"]/r["b_hi"] if r["b_hi"] else 1
            print(f"   {r['field']:<9}{('%.4g / %.4g'%(r['b_lo'],r['b_hi'])):>20} -> {r['after']:<10.4g}"
                  f"{'' if abs(k2-1)<1e-6 else 'x%.2f'%k2}")
    print(f"   → 预估面板操控 {54.63*h77['after']+38.80:.0f}   抬轮指数 {g['after']*abs(cg)/tr:.4f}")
print(f"\n总改动字节 {len(diff)}")
if a.apply:
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if not (out/"CarPhysics.gdb.orig").exists(): (out/"CarPhysics.gdb.orig").write_bytes(raw)
    (out/"CarPhysics.gdb").write_bytes(bytes(buf))
    c=(GDB/"CarChassis.gdb").read_bytes()
    (out/"CarChassis.gdb").write_bytes(c); (out/"CarChassis.gdb.orig").write_bytes(c)
    (out/"plan-report.json").write_text(json.dumps(
        {"cars":{k:{"full":p["full"],"style":p["style"],"offset":f"0x{p['off']:X}","rows":p["rows"]}
                 for k,p in plan.items()},"changed_bytes":len(diff),"sha256":sha(bytes(buf))},
        ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"已写出 {out}")
