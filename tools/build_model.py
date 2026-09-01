#!/usr/bin/env python3
"""Build the A9 physics model: field table + per-car archive."""
import struct, json, re
import numpy as np
from pathlib import Path

A9  = Path(r"C:\Users\player\Desktop\A9 sifugc")
OUT = Path(r"C:\Users\player\Desktop\a9模型")
cp     = (A9/"project/scratch/reference/vehicle-gdb/CarPhysics.gdb").read_bytes()
cardef = (A9/"project/scratch/reference/vehicle-gdb/CarDef.gdb").read_bytes()
biz    = (A9/"project/scratch/reference/gdb/A9-business.gdb").read_bytes()

def descriptors(d):
    for co in range(max(0,len(d)-32*2000), len(d)-3, 4):
        c = struct.unpack_from("<I", d, co)[0]
        if not 1 <= c <= 2000 or co+4+c*32 != len(d): continue
        t=co+4
        return [dict(zip(("i","key","off","size","tag"),(i,)+struct.unpack_from("<QQQQ",d,t+i*32))) for i in range(c)]
    raise SystemExit
descs = descriptors(cp)
base  = [d for d in descs if d["size"]==428 and d["tag"]==0x83C70E66]
SENNA = 0x11800

# name linkage
keypos={}
for d in base:
    p=cardef.find(struct.pack("<Q", d["key"]))
    if p>=0: keypos[p]=d
kp=np.array(sorted(keypos)); cardef_lc=cardef.lower()
cars={}
for m in re.finditer(rb"[A-Za-z0-9][ -~]{2,48}", biz):
    st,en=m.start(),m.end()
    if st<12: continue
    cid,z,n=struct.unpack_from("<III",biz,st-12)
    if z or n!=en-st: continue
    p=en+33
    try:
        nt=struct.unpack_from("<I",biz,p)[0]
        if nt>64: continue
        s=struct.unpack_from("<5Q",biz,p+4+8*nt)
    except Exception: continue
    if not (500<=s[0]<=60000 and s[0]<=s[1]<=60000): continue
    if not (100<=s[3]<=20000 and s[3]<=s[4]<=20000): continue
    cars[m.group().decode()]=dict(cid=cid,rank_lo=s[0],rank_hi=s[1],ts_lo=s[3]/10,ts_hi=s[4]/10)
name_of={}
used=set()
for name,v in cars.items():
    pos=cardef_lc.find(name.lower().encode())
    if pos<0: continue
    j=np.searchsorted(kp,pos)
    if j>=len(kp): continue
    k=int(kp[j])
    if k-pos>0x400: continue
    d=keypos[k]
    if d["off"] in used: continue
    used.add(d["off"]); name_of[d["off"]]=(name,v)

F=np.array([struct.unpack_from("<107f",cp,d["off"]) for d in base])
U=np.array([struct.unpack_from("<107I",cp,d["off"]) for d in base])
offs=[d["off"] for d in base]; si=offs.index(SENNA)

KNOWN={22:"ground_speed_low",23:"ground_speed_high",
 32:"nitro1_A_lo",33:"nitro1_A_hi",34:"nitro1_drain_lo",35:"nitro1_drain_hi",36:"nitro1_spd_lo",37:"nitro1_spd_hi",38:"nitro1_D_lo",39:"nitro1_D_hi",
 40:"nitro2_A_lo",41:"nitro2_A_hi",42:"nitro2_drain_lo",43:"nitro2_drain_hi",44:"nitro2_spd_lo",45:"nitro2_spd_hi",46:"nitro2_D_lo",47:"nitro2_D_hi",
 48:"nitro3_A_lo",49:"nitro3_A_hi",50:"nitro3_drain_lo",51:"nitro3_drain_hi",52:"nitro3_spd_lo",53:"nitro3_spd_hi",54:"nitro3_D_lo",55:"nitro3_D_hi",
 56:"nitro4_A_lo",57:"nitro4_A_hi",58:"nitro4_drain_lo",59:"nitro4_drain_hi",60:"nitro4_spd_lo",61:"nitro4_spd_hi",
 72:"accel_low",73:"accel_high",78:"tyre_force_low",79:"tyre_force_high",
 99:"compression_damping",100:"rebound_damping"}

# int64 detection: raw < 2^24 for all cars, and next slot is all-zero
def is_int(i):  return bool(np.all(U[:,i] < (1<<24)))
def all_zero(i):return bool(np.all(U[:,i]==0))
types={}
i=0
while i < 107:
    if is_int(i) and not all_zero(i) and i+1<107 and all_zero(i+1):
        types[i]="int64"; types[i+1]="(hi32)"; i+=2
    else:
        types[i]="int32" if (is_int(i) and not all_zero(i)) else "float"; i+=1

lk=[(o,v) for o,v in name_of.items()]
idxs=[offs.index(o) for o,_ in lk]
ts=np.array([v[1]["ts_hi"] for _,v in lk]); rk=np.array([v[1]["rank_hi"] for _,v in lk])
def corr(c,y):
    c=c[idxs]
    return 0.0 if np.std(c)==0 or np.std(y)==0 else float(np.corrcoef(c,y)[0,1])

rows=[]
for i in range(107):
    t=types[i]
    val=U[:,i].astype(np.float64) if t.startswith("int") else F[:,i].astype(np.float64)
    rows.append(dict(idx=i, byte=f"0x{i*4:X}", type=t, name=KNOWN.get(i,""),
        distinct=int(len(np.unique(val))), min=float(val.min()), max=float(val.max()),
        senna=float(val[si]), r_topspeed=round(corr(val,ts),4), r_rank=round(corr(val,rk),4)))
json.dump(rows, open(OUT/"02-字段表"/"carphysics-107-fields.json","w",encoding="utf-8"), indent=1, ensure_ascii=False)

archive={}
for d in base:
    o=d["off"]; nm=name_of.get(o,(None,None))
    archive[f"0x{d['key']:X}"]=dict(record_offset=f"0x{o:X}", descriptor=d["i"],
        name=nm[0], business=nm[1],
        fields={str(i): (int(U[offs.index(o),i]) if types[i].startswith("int") else round(float(F[offs.index(o),i]),6)) for i in range(107)})
json.dump(archive, open(OUT/"03-车辆档案"/"carphysics-428B-cohort.json","w",encoding="utf-8"), indent=1, ensure_ascii=False)

print(f"fields -> 02-字段表/carphysics-107-fields.json   ({len(rows)} rows)")
print(f"archive-> 03-车辆档案/carphysics-428B-cohort.json ({len(archive)} cars, {len(name_of)} named)")
print(f"\nint64 slots: {[i for i,t in types.items() if t=='int64']}")
print(f"int32 slots: {[i for i,t in types.items() if t=='int32']}")
