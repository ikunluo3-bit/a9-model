#!/usr/bin/env python3
"""CarPhysics.gdb structural analysis: type, constancy, grouping, correlations."""
import struct, json, re
import numpy as np
from pathlib import Path

A9   = Path(r"C:\Users\player\Desktop\A9 sifugc")
CP   = A9/"project/scratch/reference/vehicle-gdb/CarPhysics.gdb"
CD   = A9/"project/scratch/reference/vehicle-gdb/CarDef.gdb"
BIZ  = A9/"project/scratch/reference/gdb/A9-business.gdb"
OUT  = Path(r"C:\Users\player\Desktop\a9模型")

cp, cardef, biz = CP.read_bytes(), CD.read_bytes(), BIZ.read_bytes()

def descriptors(data):
    for co in range(max(0,len(data)-32*2000), len(data)-3, 4):
        cnt = struct.unpack_from("<I", data, co)[0]
        if not 1 <= cnt <= 2000: continue
        if co + 4 + cnt*32 != len(data): continue
        t = co+4
        return [dict(zip(("i","key","off","size","tag"),
                (i,)+struct.unpack_from("<QQQQ", data, t+i*32))) for i in range(cnt)]
    raise SystemExit("no descriptor table")

descs = descriptors(cp)
base  = [d for d in descs if d["size"]==428 and d["tag"]==0x83C70E66]

# --- link CarPhysics -> car name via CarDef, and name -> business stats ---
keypos = {}
for d in base:
    p = cardef.find(struct.pack("<Q", d["key"]))
    if p >= 0: keypos[p] = d
kp = np.array(sorted(keypos))
cardef_lc = cardef.lower()

cars = {}
for m in re.finditer(rb"[A-Za-z0-9][ -~]{2,48}", biz):
    st, en = m.start(), m.end()
    if st < 12: continue
    cid, z, n = struct.unpack_from("<III", biz, st-12)
    if z or n != en-st: continue
    p = en + 33
    try:
        nt = struct.unpack_from("<I", biz, p)[0]
        if nt > 64: continue
        s = struct.unpack_from("<5Q", biz, p+4+8*nt)
    except Exception: continue
    if not (500 <= s[0] <= 60000 and s[0] <= s[1] <= 60000): continue
    if not (100 <= s[3] <= 20000 and s[3] <= s[4] <= 20000): continue
    cars[m.group().decode()] = dict(cid=cid, rank_hi=s[1], ts_lo=s[3]/10, ts_hi=s[4]/10)

linked = []
used=set()
for name, v in cars.items():
    pos = cardef_lc.find(name.lower().encode())
    if pos < 0: continue
    j = np.searchsorted(kp, pos)
    if j >= len(kp): continue
    k = int(kp[j])
    if k - pos > 0x400: continue
    d = keypos[k]
    if d["off"] in used: continue
    used.add(d["off"]); linked.append((d, v, name))

F = np.array([struct.unpack_from("<107f", cp, d["off"]) for d in base])          # floats
U = np.array([struct.unpack_from("<107I", cp, d["off"]) for d in base])          # raw bits
print(f"cohort: {len(base)} cars (428B) | business-linked: {len(linked)}")

# --- per-field typing ---
def classify(i):
    u, f = U[:,i], F[:,i]
    nz = u[u != 0]
    # int-like: raw bits small (<2^24) and never a plausible float exponent
    intish = np.all((u < (1<<24)))
    return "int" if intish and len(nz) else "float"

rows=[]
for i in range(107):
    f = F[:,i]; u=U[:,i]
    t = classify(i)
    val = u.astype(np.float64) if t=="int" else f.astype(np.float64)
    rows.append(dict(idx=i, type=t, distinct=int(len(np.unique(val))),
                     min=float(val.min()), max=float(val.max()),
                     senna=float(val[[d["off"] for d in base].index(0x11800)])))
json.dump(rows, open(OUT/"02-字段表"/"carphysics-fields-raw.json","w"), indent=1)

print(f"\n{'idx':>3} {'type':>5} {'distinct':>8} {'min':>13} {'max':>13} {'senna':>13}")
for r in rows:
    flag = " CONST" if r["distinct"]==1 else ""
    print(f"{r['idx']:3d} {r['type']:>5} {r['distinct']:8d} {r['min']:13.4f} {r['max']:13.4f} {r['senna']:13.4f}{flag}")
