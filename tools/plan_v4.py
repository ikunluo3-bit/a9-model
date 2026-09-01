#!/usr/bin/env python3
"""v4：D级极速锁 HUD≤350，半径全力加强。 HUD = 物理 × 1.557"""
import argparse, hashlib, json, struct, sys, io
from pathlib import Path
if sys.platform=="win32": sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
GDB=Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k")
K=1.557
CH={"三菱":(1.43,-0.100),"Z4":(1.47,-0.160),"370Z":(1.785,-0.160),"拉法":(1.68,-0.150)}
# 车 -> (全名, 记录, 风格, HUD目标, 转向锐度, 抓地, 操控77, 阻尼)
CARS={
 "三菱":("三菱 Lancer Evolution",0x1CE90,"轨道压路机",348.0, 88000.0,1.05,1.00,0.60),
 "Z4": ("宝马 Z4 LCI E89",      0x1933C,"翘头刀",    348.0, 88000.0,1.05,1.00,0.45),
 "370Z":("日产 370Z",           0x19BB0,"轻量刀锋",  348.0,100000.0,1.05,1.00,0.50),
 "拉法":("法拉利 LaFerrari",    0x1FBEC,"全能旗舰",  430.0, 88000.0,1.10,1.00,0.50),
}
NITRO=[("单喷消耗",34,35,12.75,"d"),("单喷加成",36,37,4.229,"u"),("单喷维持",38,39,1850.0,"u"),
       ("橙喷消耗",42,43,25.5,"d"),("橙喷加成",44,45,12.69,"u"),("橙喷维持",46,47,1150.0,"u"),
       ("蓝喷消耗",50,51,32.62,"d"),("蓝喷加成",52,53,8.457,"u"),("蓝喷维持",54,55,7200.0,"u"),
       ("紫喷消耗",58,59,34.0,"d"),("紫喷加成",60,61,16.91,"u")]
def f32(v): return struct.unpack("<f",struct.pack("<f",v))[0]
raw=(GDB/"CarPhysics.gdb").read_bytes(); buf=bytearray(raw)
def rd(o,i): return struct.unpack_from("<f",raw,o+i*4)[0]
plan={}; touched=set()
for k,(full,off,style,hud,steer,grip,f77,damp) in CARS.items():
    gs=hud/K
    rows=[]
    def put(nm,lo,hi,new): rows.append(dict(field=nm,lo=lo,hi=hi,b_lo=rd(off,lo),b_hi=rd(off,hi),after=f32(new)))
    put("极速",22,23,gs); put("加速",72,73,2.6); put("抓地",78,79,grip)
    put("转向锐度",19,21,steer); put("转向锐度2",14,16,steer*0.75)
    put("操控76",76,76,0.60); put("操控77",77,77,f77)
    put("压缩阻尼",99,99,max(rd(off,99),damp)); put("回弹阻尼",100,100,max(rd(off,100),damp))
    for nm,lo,hi,t,d in NITRO:
        cur=rd(off,hi); put(nm,lo,hi, max(cur,t) if d=="u" else min(cur,t))
    plan[k]=dict(full=full,off=off,style=style,rows=rows,hud=hud,gs=gs)
    for r in rows:
        for idx in {r["lo"],r["hi"]}:
            b=off+idx*4; struct.pack_into("<f",buf,b,r["after"]); touched|=set(range(b,b+4))
diff={i for i,(a,b) in enumerate(zip(raw,buf)) if a!=b}
stray=sorted(x for x in diff if x not in touched)
if stray: sys.exit(f"越界 {[hex(x) for x in stray[:6]]}")
ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true")
ap.add_argument("--out",default=r"C:\Users\player\Desktop\a9模型\tuned-v4")
a=ap.parse_args()
print(f"{'车':<22}{'HUD极速':>9}{'物理':>8}{'转向锐度':>10}{'抓地':>7}{'操控77':>8}{'预估操控':>9}{'抬轮':>8}")
for k,p in plan.items():
    tr,cg=CH[k]
    g=[r for r in p["rows"] if r["field"]=="抓地"][0]["after"]
    st=[r for r in p["rows"] if r["field"]=="转向锐度"][0]["after"]
    h=[r for r in p["rows"] if r["field"]=="操控77"][0]["after"]
    print(f"{p['full'][:20]:<22}{p['hud']:9.0f}{p['gs']:8.1f}{st:10.0f}{g:7.2f}{h:8.2f}{54.63*h+38.80:9.0f}{g*abs(cg)/tr:8.4f}")
print(f"\n总改动字节 {len(diff)}")
if a.apply:
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if not (out/"CarPhysics.gdb.orig").exists(): (out/"CarPhysics.gdb.orig").write_bytes(raw)
    (out/"CarPhysics.gdb").write_bytes(bytes(buf))
    c=(GDB/"CarChassis.gdb").read_bytes()
    (out/"CarChassis.gdb").write_bytes(c); (out/"CarChassis.gdb.orig").write_bytes(c)
    (out/"plan-report.json").write_text(json.dumps(
        {"K_hud_per_physical":K,"cars":{k:{"full":p["full"],"hud":p["hud"],"offset":f"0x{p['off']:X}","rows":p["rows"]}
         for k,p in plan.items()},"changed_bytes":len(diff)},ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"已写出 {out}")
