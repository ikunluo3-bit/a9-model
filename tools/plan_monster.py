#!/usr/bin/env python3
"""四台车魔改：满改 + 全项拉到全库顶层水平（不超出游戏已有区间）。

目标值取自现役最强车，不自造超界数值：
  极速357/加速2.6/抓地1.153 = Devel Sixteen
  氮气加成 = Bugatti Chiron Super Sport 300
  蓝喷维持7200 = Devel Sixteen ; 蓝喷消耗32.62 = Agera RS(最省)
转向锐度：各车原值若已高于目标则保留（三菱42000 / 370Z 45000 本就靠前）
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys, io
from pathlib import Path
if sys.platform=="win32":
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
GDB=Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k")
CARS={"三菱 Lancer Evolution":0x1CE90,"宝马 Z4 LCI E89":0x1933C,
      "日产 370Z":0x19BB0,"法拉利 LaFerrari":0x1FBEC}
CHASSIS={"三菱 Lancer Evolution":(1.43,-0.100),"宝马 Z4 LCI E89":(1.47,-0.160),
         "日产 370Z":(1.785,-0.160),"法拉利 LaFerrari":(1.68,-0.150)}
# 名字 -> (lo,hi,目标值,方向)
PLAN=[("极速",22,23,357.0,"up"),("加速",72,73,2.6,"up"),("抓地",78,79,1.153,"up"),
      ("转向锐度",19,21,56500.0,"up"),
      ("单喷消耗",34,35,12.75,"down"),("单喷加成",36,37,4.229,"up"),("单喷维持",38,39,1850.0,"up"),
      ("橙喷消耗",42,43,25.5,"down"),("橙喷加成",44,45,12.69,"up"),("橙喷维持",46,47,1150.0,"up"),
      ("蓝喷消耗",50,51,32.62,"down"),("蓝喷加成",52,53,8.457,"up"),("蓝喷维持",54,55,7200.0,"up"),
      ("紫喷消耗",58,59,34.0,"down"),("紫喷加成",60,61,16.91,"up")]
DAMP=[("压缩阻尼",99),("回弹阻尼",100)]; DAMP_FLOOR=0.45
def f32(v): return struct.unpack("<f",struct.pack("<f",v))[0]
def sha(b): return hashlib.sha256(b).hexdigest().upper()
def build():
    raw=(GDB/"CarPhysics.gdb").read_bytes(); buf=bytearray(raw)
    def rd(o,i): return struct.unpack_from("<f",raw,o+i*4)[0]
    plan={}
    for car,off in CARS.items():
        rows=[]
        for nm,lo,hi,tgt,dr in PLAN:
            cur=rd(off,hi)
            new = max(cur,tgt) if dr=="up" else min(cur,tgt)
            rows.append(dict(field=nm,lo=lo,hi=hi,before_lo=rd(off,lo),before_hi=cur,after=f32(new)))
        for nm,i in DAMP:
            cur=rd(off,i)
            rows.append(dict(field=nm,lo=i,hi=i,before_lo=cur,before_hi=cur,after=f32(max(cur,DAMP_FLOOR))))
        plan[car]=dict(offset=off,rows=rows)
    touched=set()
    for car,p in plan.items():
        for r in p["rows"]:
            for idx in {r["lo"],r["hi"]}:
                b=p["offset"]+idx*4; struct.pack_into("<f",buf,b,r["after"]); touched|=set(range(b,b+4))
    diff={i for i,(a,b) in enumerate(zip(raw,buf)) if a!=b}
    stray=sorted(x for x in diff if x not in touched)
    if stray: sys.exit(f"越界: {[hex(x) for x in stray[:8]]}")
    return raw,bytes(buf),plan,len(diff)
if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true")
    ap.add_argument("--out",default=r"C:\Users\player\Desktop\a9模型\tuned-monster")
    a=ap.parse_args()
    raw,new,plan,n=build()
    for car,p in plan.items():
        tr,cg=CHASSIS[car]
        grip=[r for r in p["rows"] if r["field"]=="抓地"][0]
        w0=grip["before_hi"]*abs(cg)/tr; w1=grip["after"]*abs(cg)/tr
        print(f"\n=== {car} ===")
        print(f"  {'字段':<10}{'原 低/满':>22}{'魔改后':>12}   倍数")
        for r in p["rows"]:
            k=r["after"]/r["before_hi"] if r["before_hi"] else 1
            print(f"  {r['field']:<10}{('%.4g / %.4g'%(r['before_lo'],r['before_hi'])):>22}{r['after']:>12.4g}"
                  f"{'' if abs(k-1)<1e-6 else '   x%.2f'%k}")
        print(f"  抬轮指数 {w0:.4f} -> {w1:.4f}   (全车原厂 max 0.1216)")
    print(f"\n总改动字节: {n}")
    if a.apply:
        out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
        if not (out/"CarPhysics.gdb.orig").exists(): (out/"CarPhysics.gdb.orig").write_bytes(raw)
        (out/"CarPhysics.gdb").write_bytes(new)
        ch=(GDB/"CarChassis.gdb").read_bytes()
        (out/"CarChassis.gdb").write_bytes(ch); (out/"CarChassis.gdb.orig").write_bytes(ch)
        (out/"plan-report.json").write_text(json.dumps(
            {"cars":{c:{"offset":f"0x{p['offset']:X}","rows":p["rows"]} for c,p in plan.items()},
             "changed_bytes":n,"sha256_after":sha(new)},ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"已写出 {out}")
